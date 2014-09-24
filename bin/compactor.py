#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import urllib2
from decimal import Decimal

# get settings from args
TXFEE = Decimal('0.0001') # transaction fee per input address
LIMIT = 20 # max number of inputs/outputs per transaction
MIN_CONFIRMS = 1 # number of confirmations required for utxo inptus


def _satoshi_to_btc(satoshi):
   return satoshi / Decimal("10") ** Decimal("8")

def _get_deltas(txrequests):
  deltas = {}
  for txrequest in txrequests:
    amount = Decimal(str(txrequest["amount"]))
    # update src delta
    src = txrequest["src"]
    srcdelta = deltas.get(src) != None and deltas[src] or Decimal("0")
    deltas[src] = srcdelta - amount
    # update dest delta
    dest = txrequest["dest"]
    destdelta = deltas.get(dest) != None and deltas[dest] or Decimal("0")
    deltas[dest] = destdelta + amount
  return deltas

def _get_utxo(address):
  # source ngcccbase/services/blockchain.py
  url = "https://blockchain.info/unspent?active=%s" % address
  try:
    def reformat(output):
      return {
        "address": address,
        "txid": output['tx_hash'],
        "vout": output['tx_output_n'],
        "amount": _satoshi_to_btc(Decimal(output['value'])),
        "script": output['script'],
      }
    outputs = json.loads(urllib2.urlopen(url).read())['unspent_outputs']
    outputs = filter(lambda x: x["confirmations"] >= MIN_CONFIRMS, outputs)
    return map(reformat, outputs)
  except urllib2.HTTPError as e:
    if e.code == 500:
      return []
    raise

def _sum_unspents(unspents):
  return sum(map(lambda x: Decimal(str(x["amount"])), unspents))

def compress(txrequests):
  """
  Very simple implementation that assumes all requests are not malacious ...
  Args:
      txrequests: [{ "src" : src, "dest" : dest, "amount" : amount }, ...]
      limit: the grouping size limit
  """
  deltas = _get_deltas(txrequests).items()
  src_deltas = filter(lambda x: x[1] < Decimal("0"), deltas)
  dests_deltas = filter(lambda x: x[1] > Decimal("0"), deltas)
  src_unspents = map(lambda x: (x[0], _get_utxo(x[0])), src_deltas)
  src_balances = dict(map(lambda x: (x[0], _sum_unspents(x[1])), src_unspents))

  # tx fee only for net senders, thus encuraging paying it forward
  get_change = lambda x: (x[0], src_balances[x[0]] + x[1] - TXFEE)
  src_changes = map(lambda x: get_change(x), src_deltas)
  src_changes = filter(lambda x: x[1] > Decimal("0"), src_changes)

  inputs = reduce(lambda a, b: a + b, map(lambda x: x[1], src_unspents))
  outputs = dests_deltas + src_changes
  input_amount = sum(map(lambda x: x["amount"], inputs))
  output_amount = sum(map(lambda x: x[1], outputs))
  fees = input_amount - output_amount
  savings = (TXFEE * len(txrequests)) - fees
  return {
      "inputs" : inputs, 
      "outputs" : outputs, 
      "fees" : fees, 
      "input_amount" : input_amount,
      "output_amount" : output_amount,
      "savings" : savings,
  }

def partition(transaction, limit):
  pass # TODO recursivly partition until under limit

if __name__ == "__main__":
  #print json.load(sys.stdin)
  transaction = compress(json.load(sys.stdin))
  print transaction
  #print partition(transaction, LIMIT)

