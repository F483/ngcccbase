#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pyjsonrpc
import json

PROCESS_BLOCKS = 20 # TODO get from arg
MIN_OCCURANCES = 2 # TODO get from arg

rpc = pyjsonrpc.HttpClient(
  url = "http://127.0.0.1:8332", # TODO testnet option
  username = "bitcoinrpcuser",
  password = "bitcoinrpcpass"
)

logs = []
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
      log = {
        "src" : src, 
        "dest" : out["scriptPubKey"]["addresses"][0],
        "amount" : out["value"]
      }
      occurances[log["src"]] = getcount(log["src"]) + 1
      occurances[log["dest"]] = getcount(log["dest"]) + 1
      result.append(log)
    return result
  except: # ignore everything else
    return []

# process blocks
blockcount = rpc.getblockcount()
blockindexes = range(blockcount + 1 - PROCESS_BLOCKS, blockcount + 1)
for blockhash in map(rpc.getblockhash, blockindexes):
  for txid in rpc.getblock(blockhash)["tx"]:
    logs += process_tx(txid)

# filter occurances
def minoccurances(log):
  return (
    occurances[log["src"]] >= MIN_OCCURANCES or 
    occurances[log["dest"]] >= MIN_OCCURANCES
  )
print len(logs)
logs = filter(minoccurances, logs)

# print output
print json.dumps({
  "logs" : logs
})

