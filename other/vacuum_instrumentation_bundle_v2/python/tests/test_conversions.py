from vacuum_instruments.analog import gp475_voltage_to_pressure,pdr_d1_voltage_to_pressure

def test_gp475():
    assert abs(gp475_voltage_to_pressure(4.0).pressure-1.0)<1e-12
    assert abs(gp475_voltage_to_pressure(5.0).pressure-10.0)<1e-12
    assert not gp475_voltage_to_pressure(10.0).valid

def test_pdr():
    assert pdr_d1_voltage_to_pressure(5.0,100.0).pressure==50.0
