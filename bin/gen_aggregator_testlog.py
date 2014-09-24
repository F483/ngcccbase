#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pyjsonrpc
import json

PROCESS_BLOCKS = 20 # TODO get from arg
MIN_OCCURANCES = 3 # TODO get from arg

rpc = pyjsonrpc.HttpClient(
  url = "http://127.0.0.1:8332", # TODO testnet option
  username = "bitcoinrpcuser",
  password = "bitcoinrpcpass"
)

txrequests = []
occurances = {}
getcount = lambda address: occurances.get(address) and occurances[address] or 0

def process_tx(txid):
  try: # only add very simple transactions and ignore the rest
    transaction = rpc.decoderawtransaction(rpc.getrawtransaction(txid))
    if len(transaction["vin"]) > 1:
      return []
    srctxid = transaction["vin"][0]["txid"]
    srcvout = transaction["vin"][0]["vout"]
    srctransaction = rpc.decoderawtransaction(rpc.getrawtransaction(srctxid))
    src = srctransaction["vout"][srcvout]["scriptPubKey"]["addresses"][0]
    result = []
    for out in transaction["vout"]:
      txrequest = {
        "src" : src, 
        "dest" : out["scriptPubKey"]["addresses"][0],
        "amount" : out["value"]
      }
      occurances[txrequest["src"]] = getcount(txrequest["src"]) + 1
      occurances[txrequest["dest"]] = getcount(txrequest["dest"]) + 1
      result.append(txrequest)
    return result
  except: # ignore everything else
    return []

# process blocks
blockcount = rpc.getblockcount()
blockindexes = range(blockcount + 1 - PROCESS_BLOCKS, blockcount + 1)
for blockhash in map(rpc.getblockhash, blockindexes):
  for txid in rpc.getblock(blockhash)["tx"]:
    txrequests += process_tx(txid)

# filter occurances
#print len(txrequests) # BEFORE
def minoccurances(txrequest):
  return (
    occurances[txrequest["src"]] >= MIN_OCCURANCES or 
    occurances[txrequest["dest"]] >= MIN_OCCURANCES
  )
txrequests = filter(minoccurances, txrequests)
#print len(txrequests) # AFTER

print json.dumps(txrequests)

