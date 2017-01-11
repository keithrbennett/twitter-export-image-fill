#!/usr/bin/env python

'''
Twitter export image fill 1.02
by Marcin Wichary (aresluna.org)

Site: https://github.com/mwichary/twitter-export-image-fill

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

For more information, please refer to <http://unlicense.org/>
'''

import argparse
import json
import os
import pprint
import re
import sys
import time
import urllib
from shutil import copyfile

# Introduce yourself
print "Twitter export image fill 1.02"
print "by Marcin Wichary (aresluna.org)"
print "use --help to see options"
print

pprinter = pprint.PrettyPrinter(indent=4)


def stdout_print(str):
  sys.stdout.write("\r%s\033[K" % str)
  sys.stdout.flush()


def year_month_str(date):

  year_str = '%04d' % date['year']
  month_str = '%02d' % date['month']
  return "%s_%s" % (year_str, month_str)


def parse_arguments():
  parser = argparse.ArgumentParser(description = 'Downloads all the images to your Twitter archive .')
  parser.add_argument('--include-retweets', action='store_true',
  help = 'download images of retweets in addition to your own tweets')
  parser.add_argument('--continue-from', dest='EARLIER_ARCHIVE_PATH',
  help = 'use images downloaded into an earlier archive instead of downloading them again (useful for incremental backups)')
  return parser.parse_args()


# If an earlier archive has been specified, check whether or not it actually exists
# (This is important because failure would mean quietly downloading all the files again)
def process_earlier_archive_path(args):

  earlier_archive_path = args.EARLIER_ARCHIVE_PATH

  if earlier_archive_path:
    try:
      os.stat(os.path.join(earlier_archive_path, "data", "js", "tweet_index.js"))
    except:
      print "Could not find the earlier archive!"
      print "Make sure you're pointing at the directory that contains the index.html file."
      sys.exit(-4)

  return earlier_archive_path


# Process the index file to see what needs to be done
def read_index():
  index_filename =  os.path.join("data", "js", "tweet_index.js")
  try:
    with open(index_filename) as index_file:
      index_str = index_file.read()

      index_str = re.sub(r'var tweet_index =', '', index_str)
      index = json.loads(index_str)
      return index

  except:
    print "Could not open the data file!"
    print "Please run this script from your tweet archive directory"
    print "(the one with index.html file)."
    print
    sys.exit(-1)


# Make a copy of the original JS file in backup_filename, just in case (only if it doesn't exist before)
def create_filenames(date):
  ym_str = year_month_str(date)

  data_filename = os.path.join(tweet_dir, "%s.js" % (ym_str))

  # Make a copy of the original JS file, just in case (only if it doesn't exist before)
  backup_filename = os.path.join(tweet_dir, "%s_original.js" % (ym_str))

  media_directory_name = os.path.join(tweet_dir, "%s_media" % (ym_str))

  return [data_filename, backup_filename, media_directory_name]


def copy_file_if_absent(source, destination):
  try:
    os.stat(destination)
  except:
    copyfile(source, destination)


def mkdir_if_absent(dir):
  try:
    os.stat(dir)
  except:
    os.mkdir(dir)


def read_month_data_file(data_filename):
  with open(data_filename) as data_file:
    data_str = data_file.read()
    # Remove the assignment to a variable that breaks JSON parsing,
    # but save for later since we have to recreate the file
    first_data_line = re.match(r'Grailbird.data.tweets_(.*) =', data_str).group(0)
    data_str = re.sub(first_data_line, '', data_str)
    data = json.loads(data_str)
    return [data, first_data_line]



def media_already_downloaded(media):
  return os.path.isfile(media['media_url'])


def is_retweet(tweet):
  return 'retweeted_status' in tweet.keys()


def reformat_date_string(string):
  string = re.sub(r':', '.', string)
  string = re.sub(r' ', '_', string)
  return string


def download_file(url, local_filename):
  downloaded = False
  download_tries = 3
  while not downloaded:
    # Actually download the file!
    try:
      urllib.urlretrieve(url, local_filename)
    except:
      download_tries -= 1
      if download_tries == 0:
        print
        print "Failed to download %s after 3 tries." % url
        print "Please try again later?"
        sys.exit(-2)
      time.sleep(5)  # Wait 5 seconds before retrying
    else:
      return True
# Move return to try block and remove else?
# Replace downloaded var w/download_tries in while expression?


def process_month(date):

  year_month_display_str = "%04d/%02d" % (date['year'], date['month'])

  try:
    data_filename, backup_filename, media_directory_name = create_filenames(date)

    copy_file_if_absent(data_filename, backup_filename)

    # Loop 2: Go through all the tweets in a month
    # --------------------------------------------

    tweets_this_month, first_data_line = read_month_data_file(data_filename)

    tweet_count_for_month = len(tweets_this_month)
    image_count_for_month = 0

    stdout_print("%s: %i tweets to process..." % (year_month_display_str, tweet_count_for_month))

    for tweet_num, tweet in enumerate(tweets_this_month):

      # Don't save images from retweets
      if (not args.include_retweets) and is_retweet(tweet):
        continue

      if tweet['entities']['media']:
        image_count_for_tweet = 1

        # Build a tweet date string to be used in the filename prefix
        # (only first 19 characters + replace colons with dots)
        date_str = reformat_date_string(tweet['created_at'][:19])

        # Loop 3: Go through all the media in a tweet
        # -------------------------------------------

        for media in tweet['entities']['media']:
          if not media_already_downloaded(media):

            media_url = media['media_url_https']
            extension = os.path.splitext(media_url)[1]

            mkdir_if_absent(media_directory_name)

            # Download the original/best image size, rather than the default one
            media_url_original_resolution = media_url + ':orig'

            local_filename = os.path.join("data", "js", "tweets",
                    "%s_media" % (year_month_str(date)),
                    "%s-%s-%s%s%s" % (date_str, tweet['id'], ('rt-' if is_retweet(tweet) else ''),
                    image_count_for_tweet, extension))

            # If using an earlier archive as a starting point, try to find the desired
            # image file there first, and copy it if present
            can_be_copied = earlier_archive_path and os.path.isfile(os.path.join(earlier_archive_path, local_filename))

            stdout_print("  [%i/%i] %s %s..." %
                (tweet_num, tweet_count_for_month, "Copying" if can_be_copied else "Downloading", media_url))

            if can_be_copied:
              copyfile(earlier_archive_path + local_filename, local_filename)
            else:
              download_file(media_url_original_resolution, local_filename)

            # Rewrite the original JSON file so that the archive's index.html
            # will now point to local files... and also so that the script can
            # continue from last point
            media['media_url_orig'] = media['media_url']
            media['media_url'] = local_filename

            # Writing to a separate file so that we can only copy over the
            # main file when done
            data_filename_temp = os.path.join("data", "js", "tweets", "%s.js.tmp" % (year_month_str(date)))
            with open(data_filename_temp, 'w') as f:
              f.write(first_data_line)
              json.dump(tweets_this_month, f, indent=2)
            os.remove(data_filename)
            os.rename(data_filename_temp, data_filename)

            image_count_for_tweet += 1
            image_count_for_month += 1

        # End loop (images in a tweet)

    # End loop (tweets in a month)


    stdout_print(
        "%s: %4i tweets processed, %4i images downloaded.\n"
        % (year_month_display_str, tweet_count_for_month, image_count_for_month))
    return image_count_for_month

  # Nicer support for Ctrl-C
  except KeyboardInterrupt:
    print
    print "Interrupted! Come back any time."
    sys.exit(-3)


def main():

  global tweet_dir
  tweet_dir = os.path.join("data", "js", "tweets")

  global args
  args = parse_arguments()

  global earlier_archive_path
  earlier_archive_path = process_earlier_archive_path(args)

  tweets_by_month = read_index()

  print "To process: %i months worth of tweets..." % (len(tweets_by_month))
  print "(You can cancel any time. Next time you run, the script should resume at the last point.)"
  print

  total_image_count = 0
  for month in tweets_by_month:
    total_image_count += process_month(month)


  print
  print "Done!"
  print "%i images downloaded in total." % total_image_count
  print


# ========================
main()
# ========================
