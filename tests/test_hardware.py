from jarvis_local.hardware import Hardware, snapshot


def test_snapshot_fields_positive():
    hw = snapshot()
    assert isinstance(hw, Hardware)
    assert hw.ram_total_gb > 0 and hw.ram_free_gb > 0
    assert hw.disk_free_gb > 0 and hw.cpus > 0
    assert hw.gpu is None or isinstance(hw.gpu, str)
