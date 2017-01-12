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
def output_initial_greeting():
  print "Twitter export image fill 1.02"
  print "by Marcin Wichary (aresluna.org)"
  print "use --help to see options"
  print


def stdout_print(str):
  sys.stdout.write("\r%s\033[K" % str)
  sys.stdout.flush()


def year_month_str(date):
  year_str  = '%04d' % date['year']
  month_str = '%02d' % date['month']
  return "%s_%s" % (year_str, month_str)


def parse_arguments():
  parser = argparse.ArgumentParser(description = 'Downloads all the images to your Twitter archive .')

  parser.add_argument('--include-retweets', action='store_true',
      help = 'download images of retweets in addition to your own tweets')

  parser.add_argument('--continue-from', dest='EARLIER_ARCHIVE_PATH',
      help = 'use images downloaded into an earlier archive instead of downloading them again (useful for incremental backups)')

  return parser.parse_args()


# If an earlier archive has been specified, check whether or not it actually exists.
# (This is important because failure would mean quietly downloading all the files again.)
def process_earlier_archive_path(args):

  earlier_archive_path = args.EARLIER_ARCHIVE_PATH

  if earlier_archive_path and not os.path.exists(
          os.path.join(earlier_archive_path, tweet_index_filespec)):
    print "Could not find the earlier archive!"
    print "Make sure you're pointing at the directory that contains the index.html file."
    sys.exit(error_codes['EARLIER_ARCHIVE_MISSING'])

  return earlier_archive_path


# Process the index file to see what needs to be done
def read_index():
  try:
    with open(tweet_index_filespec) as index_file:
      index_str = index_file.read()
      index_str = re.sub(r'var tweet_index =', '', index_str)
      index = json.loads(index_str)
      return index

  except:
    print "Could not open the data file!"
    print "Please run this script from your tweet archive directory"
    print "(the one with the index.html file)."
    print
    sys.exit(error_codes['INDEX_FILE_MISSING'])


def create_filenames(date):
  ym_str = year_month_str(date)

  # example: data/js/tweets/2017_01.js
  data_filename = os.path.join(tweet_dir, "%s.js" % (ym_str))

  # Make a copy of the original JS file, just in case (only if it doesn't exist before)
  # example: data/js/tweets/2017_01_original.js
  backup_filename = os.path.join(tweet_dir, "%s_original.js" % (ym_str))

  # example: data/js/tweets/2017_01_media
  media_directory_name = os.path.join(tweet_dir, "%s_media" % (ym_str))

  return [data_filename, backup_filename, media_directory_name]



def read_month_data_file(data_filename):
  with open(data_filename) as data_file:
    data_str = data_file.read()

    # First line will look like this:
    # Grailbird.data.tweets_2017_01 =[
    #
    # Remove the assignment to a variable that breaks JSON parsing
    # (everything to the left of '['),
    # but save for later since we have to recreate the file.
    first_data_line = re.match(r'Grailbird.data.tweets_(.*) =', data_str).group(0)
    data_str = re.sub(first_data_line, '', data_str)
    data = json.loads(data_str)
    return [data, first_data_line]


def media_already_downloaded(media):
  return os.path.isfile(media['media_url'])


def is_retweet(tweet):
  return 'retweeted_status' in tweet.keys()


# Replace ':' with '.', spaces with underscores.
def reformat_date_string_for_filename(string):
  string = re.sub(r':', '.', string)
  string = re.sub(r' ', '_', string)
  return string


def download_file(url, local_filename):

  download_tries = 3
  for i in range(1, download_tries + 1):
    try:
      urllib.urlretrieve(url, local_filename) # Actually download the file!
      return True
    except:
      if i < download_tries:
        time.sleep(5)  # Wait 5 seconds before retrying
      else:
        print
        print "Failed to download %s after 3 tries." % url
        print "Please try again later?"
        sys.exit(error_codes['DOWNLOAD_FAILED'])


def media_locators(tweet, media, date, date_str, tweet_image_num):
  media_url = media['media_url_https']

  extension = os.path.splitext(media_url)[1]

  # Download the original/best image size, rather than the default one
  media_url_original_resolution = media_url + ':orig'

  local_filename = os.path.join("data", "js", "tweets",
                                "%s_media" % (year_month_str(date)),
                                "%s-%s-%s%d%s" % (date_str, tweet['id'], ('rt-' if is_retweet(tweet) else ''),
                                                  tweet_image_num, extension))
  return [media_url, media_url_original_resolution, local_filename]


def rewrite_js_file(data_filename, first_data_line, tweets_this_month, date):
  # Writing to a separate file so that we can only copy over the
  # main file when done
  data_filename_temp = os.path.join("data", "js", "tweets", "%s.js.tmp" % (year_month_str(date)))
  with open(data_filename_temp, 'w') as f:
    f.write(first_data_line)
    json.dump(tweets_this_month, f, indent=2)
  os.remove(data_filename)
  os.rename(data_filename_temp, data_filename)


def process_tweet(tweet, tweet_num, media_directory_name, date, tweet_count_to_process):
  if not tweet['entities']['media']:
    return 0

  tweet_image_num = 1

  # Build a tweet date string to be used in the filename prefix
  # (only first 19 characters)
  date_str = reformat_date_string_for_filename(tweet['created_at'][:19])

  media_to_download = filter(
    lambda media: not media_already_downloaded(media),
    tweet['entities']['media']
  )

  if len(media_to_download) > 0 and not os.path.exists(media_directory_name):
    os.mkdir(media_directory_name)

  for media in media_to_download:

    media_url, media_url_original_resolution, local_filename = \
      media_locators(tweet, media, date, date_str, tweet_image_num)

    # If using an earlier archive as a starting point, try to find the desired
    # image file there first, and copy it if present
    can_be_copied = earlier_archive_path and os.path.isfile(os.path.join(earlier_archive_path, local_filename))

    stdout_print("  [%i/%i] %s %s..." %
                 (tweet_num, tweet_count_to_process, "Copying" if can_be_copied else "Downloading", media_url))

    if can_be_copied:
      copyfile(os.path.join(earlier_archive_path, local_filename), local_filename)
    else:
      download_file(media_url_original_resolution, local_filename)

    tweet_image_num += 1

    # Rewrite the data so that the archive's index.html
    # will now point to local files... and also so that the script can
    # continue from last point.
    media['media_url_orig'] = media['media_url']
    media['media_url'] = local_filename

  return len(media_to_download)



def process_month(date):

  year_month_display_str = "%04d/%02d" % (date['year'], date['month'])

  data_filename, backup_filename, media_directory_name = create_filenames(date)

  if not os.path.exists(backup_filename):
    copyfile(data_filename, backup_filename)

  # Loop 2: Go through all the tweets in a month
  # --------------------------------------------

  tweets_this_month, first_data_line = read_month_data_file(data_filename)

  image_count_downloaded_for_month = 0

  tweets_to_process = tweets_this_month


  if not args.include_retweets:
    # if the user has not specified that images should be retrieved for retweets
    tweets_to_process = filter(lambda tweet: not is_retweet(tweet), tweets_to_process)
  tweet_count_to_process = len(tweets_to_process)
  stdout_print("%s: %i tweets to process..." % (year_month_display_str, tweet_count_to_process))

  for tweet_num, tweet in enumerate(tweets_to_process):
    image_count_downloaded_for_month += \
        process_tweet(tweet, tweet_num, media_directory_name, date, tweet_count_to_process)

  # Rewrite the original JSON file so that the archive's index.html
  # will now point to local files... and also so that the script can
  # continue from last point.
  rewrite_js_file(data_filename, first_data_line, tweets_this_month, date)

  stdout_print(
      "%s: %4i tweets processed, %4i images downloaded.\n"
      % (year_month_display_str, tweet_count_to_process, image_count_downloaded_for_month))
  return image_count_downloaded_for_month


def setup_globals():
  global pprinter # pprinter.pprint() can be used to output objects nicely
  pprinter = pprint.PrettyPrinter(indent=4)

  global tweet_dir
  tweet_dir = os.path.join("data", "js", "tweets")

  global tweet_index_filespec
  tweet_index_filespec = os.path.join("data", "js", "tweet_index.js")

  global args
  args = parse_arguments()

  global earlier_archive_path
  earlier_archive_path = process_earlier_archive_path(args)

  global error_codes
  error_codes = {
    'EARLIER_ARCHIVE_MISSING': -1,
    'DOWNLOAD_FAILED':         -2,
    'INDEX_FILE_MISSING':      -3,
    'KEYBOARD_INTERRUPT':      -4
  }


def main():
  output_initial_greeting()
  setup_globals()
  tweets_by_month = read_index()

  print "To process: %i months worth of tweets..." % (len(tweets_by_month))
  print "(You can cancel any time. Next time you run, the script should resume at the last point.)\n"

  total_image_count = 0
  for month in tweets_by_month:
    total_image_count += process_month(month)

  print
  print "Done!"
  print "%i images downloaded in total." % total_image_count
  print


# ========================
try:
  main()
# Nicer support for Ctrl-C:
except KeyboardInterrupt:
  print
  print "Interrupted! Come back any time."
  sys.exit(error_codes['KEYBOARD_INTERRUPT'])
# ========================
