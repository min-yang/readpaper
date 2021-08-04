"""
Queries arxiv API and downloads papers (the query is a parameter).
The script is intended to enrich an existing database pickle (by default db.p),
so this file will be loaded first, and then new results will be added to it.
"""

import os
import re
import time
import pickle
import random
import argparse
import urllib.request
import feedparser

from utils import Config, safe_pickle_dump
from pymongo import MongoClient

def encode_feedparser_dict(d):
  """ 
  helper function to get rid of feedparser bs with a deep copy. 
  I hate when libs wrap simple things in their own classes.
  """
  if isinstance(d, feedparser.FeedParserDict) or isinstance(d, dict):
    j = {}
    for k in d.keys():
      j[k] = encode_feedparser_dict(d[k])
    return j
  elif isinstance(d, list):
    l = []
    for k in d:
      l.append(encode_feedparser_dict(k))
    return l
  else:
    return d

def parse_arxiv_url(url):
  """ 
  examples is http://arxiv.org/abs/1512.08756v2
  we want to extract the raw id and the version
  """
  ix = url.rfind('/')
  idversion = url[ix+1:] # extract just the id (and the version)
  parts = idversion.split('v')
  assert len(parts) == 2, 'error parsing url ' + url
  return parts[0], int(parts[1])

if __name__ == "__main__":
  client = MongoClient()
  cs_paper_abs = client.paper.cs_paper_abs
  
  # parse input arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('--search-query', type=str,
                      default='cat:cs.*',
                      help='query used for arxiv API. See http://arxiv.org/help/api/user-manual#detailed_examples')
  parser.add_argument('--start-index', type=int, default=0, help='0 = most recent API result')
  parser.add_argument('--max-index', type=int, default=10000, help='upper bound on paper index we will fetch')
  parser.add_argument('--results-per-iteration', type=int, default=100, help='passed to arxiv API')
  parser.add_argument('--wait-time', type=float, default=15.0, help='lets be gentle to arxiv API (in number of seconds)')
  parser.add_argument('--break-on-no-added', type=int, default=1, help='break out early if all returned query papers are already in db? 1=yes, 0=no')
  args = parser.parse_args()

  # misc hardcoded variables
  base_url = 'http://export.arxiv.org/api/query?' # base api query url
  print('Searching arXiv for %s' % (args.search_query, ))

  # -----------------------------------------------------------------------------
  # main loop where we fetch the new results
  print('database has %d entries at start' % (cs_paper_abs.count(), ))
  num_added_total = 0
  
  for i in range(args.start_index, args.max_index, args.results_per_iteration):
  
    print("Results %i - %i" % (i,i+args.results_per_iteration))
    query = 'search_query=%s&sortBy=lastUpdatedDate&start=%i&max_results=%i' % (args.search_query,
                                                         i, args.results_per_iteration)
    while True:
        with urllib.request.urlopen(base_url+query) as url:
          response = url.read()
        parse = feedparser.parse(response)
        if len(parse.entries) == 0:
          print('Received no results from arxiv. Rate limiting? Exiting. Restart later maybe.')
          print(response)
          time.sleep(args.wait_time)
        else:
          break
          
    num_added = 0
    num_skipped = 0
    for e in parse.entries:

      j = encode_feedparser_dict(e)

      # extract just the raw arxiv id and version for this paper
      rawid, version = parse_arxiv_url(j['id'])
      j['_id'] = rawid
      j['_version'] = version
      j['summary'] = re.sub(r'\s+', ' ', j['summary'])
      
      # add to our database if we didn't have it before, or if this is a new version
      ret = cs_paper_abs.find_one({'_id': rawid})
      if ret and ret['_version'] >= version:
        num_skipped += 1
      else:
        if ret:
            cs_paper_abs.replace_one({'_id': rawid}, j)
        else:
            cs_paper_abs.insert_one(j)
        print('Updated %s added %s' % (j['updated'], repr(j['title'])))
        num_added += 1
        num_added_total += 1

    # print some information
    print('Added %d papers, already had %d.' % (num_added, num_skipped))

    if num_added == 0 and args.break_on_no_added == 1:
      print('No new papers were added. Assuming no new papers exist. Exiting.')
      break

    print('Sleeping for %i seconds' % (args.wait_time , ))
    time.sleep(args.wait_time)


