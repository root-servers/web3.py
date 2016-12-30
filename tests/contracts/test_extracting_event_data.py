import pytest

from web3.utils.events import (
    get_event_data,
)
from web3.utils.string import (
    force_text,
)
from web3.utils.encoding import (
    decode_hex,
)


@pytest.fixture()
def Emitter(web3, EMITTER):
    return web3.eth.contract(**EMITTER)


@pytest.fixture()
def emitter(web3, Emitter, wait_for_transaction, wait_for_block):
    wait_for_block(web3)
    deploy_txn_hash = Emitter.deploy({'from': web3.eth.coinbase, 'gas': 1000000})
    deploy_receipt = wait_for_transaction(web3, deploy_txn_hash)
    contract_address = deploy_receipt['contractAddress']

    code = web3.eth.getCode(contract_address)
    assert code == Emitter.code_runtime
    return Emitter(address=contract_address)


@pytest.mark.parametrize(
    'contract_fn,event_name,call_args,expected_args',
    (
        ('logNoArgs', 'LogAnonymous', [], {}),
        ('logNoArgs', 'LogNoArguments', [], {}),
        ('logSingle', 'LogSingleArg', [12345], {'arg0': 12345}),
        ('logSingle', 'LogSingleWithIndex', [12345], {'arg0': 12345}),
        ('logSingle', 'LogSingleAnonymous', [12345], {'arg0': 12345}),
        ('logDouble', 'LogDoubleArg', [12345, 54321], {'arg0': 12345, 'arg1': 54321}),
        ('logDouble', 'LogDoubleAnonymous', [12345, 54321], {'arg0': 12345, 'arg1': 54321}),
        ('logDouble', 'LogDoubleWithIndex', [12345, 54321], {'arg0': 12345, 'arg1': 54321}),
        ('logTriple', 'LogTripleArg', [12345, 54321, 98765], {'arg0': 12345, 'arg1': 54321, 'arg2': 98765}),
        ('logTriple', 'LogTripleWithIndex', [12345, 54321, 98765], {'arg0': 12345, 'arg1': 54321, 'arg2': 98765}),
        ('logQuadruple', 'LogQuadrupleArg', [12345, 54321, 98765, 56789], {'arg0': 12345, 'arg1': 54321, 'arg2': 98765, 'arg3': 56789}),
        ('logQuadruple', 'LogQuadrupleWithIndex', [12345, 54321, 98765, 56789], {'arg0': 12345, 'arg1': 54321, 'arg2': 98765, 'arg3': 56789}),
    )
)
def test_event_data_extraction(web3,
                               emitter,
                               wait_for_transaction,
                               emitter_log_topics,
                               emitter_event_ids,
                               contract_fn,
                               event_name,
                               call_args,
                               expected_args):
    transact_fn = getattr(emitter.transact(), contract_fn)
    event_id = getattr(emitter_event_ids, event_name)
    txn_hash = transact_fn(event_id, *call_args)
    txn_receipt = wait_for_transaction(web3, txn_hash)

    assert len(txn_receipt['logs']) == 1
    log_entry = txn_receipt['logs'][0]

    event_abi = emitter._find_matching_event_abi(event_name)

    event_topic = getattr(emitter_log_topics, event_name)
    is_anonymous = event_abi['anonymous']

    if is_anonymous:
        assert event_topic not in log_entry['topics']
    else:
        assert event_topic in log_entry['topics']

    event_data = get_event_data(event_abi, log_entry)

    assert event_data['args'] == expected_args
    assert event_data['blockHash'] == txn_receipt['blockHash']
    assert event_data['blockNumber'] == txn_receipt['blockNumber']
    assert event_data['transactionIndex'] == txn_receipt['transactionIndex']
    assert event_data['address'] == emitter.address
    assert event_data['event'] == event_name


def test_dynamic_length_argument_extraction(web3,
                                            emitter,
                                            wait_for_transaction,
                                            emitter_log_topics,
                                            emitter_event_ids):
    string_0 = "this-is-the-first-string-which-exceeds-32-bytes-in-length"
    string_1 = "this-is-the-second-string-which-exceeds-32-bytes-in-length"
    txn_hash = emitter.transact().logDynamicArgs(string_0, string_1)
    txn_receipt = wait_for_transaction(web3, txn_hash)

    assert len(txn_receipt['logs']) == 1
    log_entry = txn_receipt['logs'][0]

    event_abi = emitter._find_matching_event_abi('LogDynamicArgs')

    event_topic = emitter_log_topics.LogDynamicArgs
    assert event_topic in log_entry['topics']

    string_0_topic = web3.sha3(string_0, encoding='utf8')
    assert string_0_topic in log_entry['topics']

    event_data = get_event_data(event_abi, log_entry)

    expected_args = {
        "arg0": force_text(decode_hex(string_0_topic)),
        "arg1": string_1,
    }

    assert event_data['args'] == expected_args
    assert event_data['blockHash'] == txn_receipt['blockHash']
    assert event_data['blockNumber'] == txn_receipt['blockNumber']
    assert event_data['transactionIndex'] == txn_receipt['transactionIndex']
    assert event_data['address'] == emitter.address
    assert event_data['event'] == 'LogDynamicArgs'
