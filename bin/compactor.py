#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import pyjsonrpc
import urllib2
from decimal import Decimal

# TODO get settings from args
TESTNET = False
TXFEE = Decimal('0.0001') # transaction fee per input address
AGGROGATION_LIMIT = 20 # max number of txrequests per aggregation
MIN_CONFIRMS = 1 # number of confirmations required for utxo inptus
RPC_USER = "bitcoinrpcuser"
RPC_PASS = "bitcoinrpcpass"

rpc = pyjsonrpc.HttpClient(
  url = (TESTNET and "http://127.0.0.1:18332" or "http://127.0.0.1:8332"),
  username = RPC_USER,
  password = RPC_PASS
)

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

def _get_unspent_rpc(address):
  unspents = rpc.listunspent() # TODO worth cashing
  def usable(unspent):
    correctaddress = unspent["address"] == address
    hasminconfirms = unspent["confirmations"] >= MIN_CONFIRMS
    return correctaddress and hasminconfirms
  unspents = filter(usable, unspents)
  def reformat(unspent):
    return { 
        'amount': Decimal(str(unspent["amount"])), 
        'txid': unpsent["txid"], 
        'vout': unspent["vout"] 
    }
  return map(reformat, unspents)

def _get_unspent_blockchain_info(address):
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

def get_unspent(address):
  return _get_unspent_blockchain_info(address)


def _sum_unspents(unspents):
  return sum(map(lambda x: Decimal(str(x["amount"])), unspents))

def aggregate(txrequests):
  """
  Very simple implementation that assumes all requests are not malacious ...
  Args:
      txrequests: [{ "src" : src, "dest" : dest, "amount" : amount }]
  Returns: {
      "inputs" : [{ 'amount': Decimal, 'txid': str, 'vout': int }],
      "outputs" : (address, amount),
      "fees" : Decimal,
      "input_amount" : Decimal,
      "output_amount" : Decimal,
      "savings" : Decimal,
  }
  """
  deltas = _get_deltas(txrequests).items()
  src_deltas = filter(lambda x: x[1] < Decimal("0"), deltas)
  dests_deltas = filter(lambda x: x[1] > Decimal("0"), deltas)
  src_unspents = map(lambda x: (x[0], get_unspent(x[0])), src_deltas)
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

def partition(txrequests, limit):
  # TODO partition under limit and group resends to save fees in aggregation
  return [txrequests]

def gentransaction(aggregation):
  reformat = lambda x: { "txid" : x["txid"], "vout" : x["vout"] }
  inputs = map(reformat, aggregation["inputs"])
  outputs = dict(map(lambda x: (x[0], float(x[1])), aggregation["outputs"]))
  rawtx = rpc.createrawtransaction(inputs, outputs)
  # TODO sign transactions
  return rawtx

def compress(txrequests, aggrogation_limit):
  aggrogations = map(aggregate, partition(txrequests, aggrogation_limit))
  return map(gentransaction, aggrogations)

if __name__ == "__main__":
  txrequests = json.load(sys.stdin)
  transactions = compress(txrequests, AGGROGATION_LIMIT)
  print transactions

