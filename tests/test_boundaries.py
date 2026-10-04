import pytest


@pytest.mark.parametrize('label', ['Multiplicer med', 'Er lig med', 'Divider med', 'Ryd post'])
def test_danish_calculator_known_buttons(label):
    from cua_lab.safety import classify
    action = {'tool':'click','arguments':{'pid':1,'window_id':2,'element_token':'s:1'}}
    obs = {'window':{'pid':1,'window_id':2,'window_title':'Lommeregner','elements':[{'element_token':'s:1','label':label}]}}
    assert classify(action, obs) is None
    obs['window']['window_title'] = 'Other app'
    assert classify(action, obs) is not None


def test_unknown_tool_rejected():
    from cua_lab.protocol import validate_action
    with pytest.raises(ValueError):
        validate_action({'tool': 'shell', 'arguments': {'command': 'echo unsafe'}}, {})


def test_extra_argument_rejected():
    from cua_lab.protocol import validate_action
    schemas = {'list_windows': {'type': 'object', 'properties': {}, 'additionalProperties': False}}
    with pytest.raises(ValueError):
        validate_action({'tool': 'list_windows', 'arguments': {'secret': 'x'}}, schemas)


def test_click_without_element_or_coordinates_rejected_before_native_dispatch():
    from cua_lab.protocol import validate_action
    action={'tool':'click','arguments':{'delivery_mode':'background',
            'target':{'kind':'window','pid':44524,'window_id':723626}}}
    with pytest.raises(ValueError,match='Click requires'):
        validate_action(action,{'click':{'type':'object'}})


def test_duplicate_equal_uia_targets_use_one_native_representation():
    from cua_lab.protocol import validate_action
    schema={'click':{'type':'object'}}
    args={'target':{'kind':'window','pid':1,'window_id':2},'pid':1,'window_id':2,'element_token':'s1:1'}
    assert validate_action({'tool':'click','arguments':args},schema)['arguments']=={
        'pid':1,'window_id':2,'element_token':'s1:1'}
    args['pid']=9
    with pytest.raises(ValueError,match='Conflicting'):
        validate_action({'tool':'click','arguments':args},schema)


def test_current_uia_token_has_exact_scope_without_redundant_pid():
    from cua_lab.protocol import validate_action
    from cua_lab.safety import classify
    action={'tool':'click','arguments':{'element_token':'s1:1','x':10,'y':20}}
    normalized=validate_action(action,{'click':{'type':'object'}})
    assert normalized['arguments']=={'element_token':'s1:1'}
    observation={'window':{'pid':1,'window_id':2,'window_title':'Calculator',
                           'elements':[{'element_token':'s1:1','label':'One'}]}}
    assert classify(normalized,observation) is None
    normalized['arguments']['element_token']='stale:1'
    assert classify(normalized,observation) is not None
    normalized['arguments'].update(element_token='s1:1',pid=9,window_id=10)
    assert classify(normalized,observation) is not None


def test_readonly_enforced():
    from cua_lab.safety import classify
    with pytest.raises(PermissionError):
        classify({'tool': 'click', 'arguments': {}}, {}, read_only=True)


def test_unknown_click_requires_approval():
    from cua_lab.safety import classify
    assert classify({'tool': 'click', 'arguments': {'element_token': 's1:1'}}, {})


def test_memory_rejects_arbitrary_content():
    from cua_lab.learning import Learning
    with pytest.raises(ValueError):
        Learning(application='Discord', problem='degraded_uia', strategy='visual_fallback', source_machine='a'*16, private_message='secret')


def test_memory_destination_is_not_model_controlled():
    from cua_lab.learning import Learning, knowledge_path
    record = Learning(application='Discord', problem='degraded_uia', strategy='visual_fallback', source_machine='a'*16)
    assert knowledge_path(record).startswith('cua_knowledge/machines/')
    with pytest.raises(ValueError):
        Learning(application='../../.github/workflows', problem='degraded_uia', strategy='visual_fallback', source_machine='a'*16)
