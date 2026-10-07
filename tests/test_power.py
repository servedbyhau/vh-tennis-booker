from court_booker.power import ES_CONTINUOUS, ES_SYSTEM_REQUIRED, keep_awake


def test_keep_awake_sets_and_clears_state():
    calls = []
    with keep_awake(set_state=calls.append):
        assert calls == [ES_CONTINUOUS | ES_SYSTEM_REQUIRED]
    assert calls[-1] == ES_CONTINUOUS


def test_keep_awake_clears_state_on_error():
    calls = []
    try:
        with keep_awake(set_state=calls.append):
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    assert calls[-1] == ES_CONTINUOUS
