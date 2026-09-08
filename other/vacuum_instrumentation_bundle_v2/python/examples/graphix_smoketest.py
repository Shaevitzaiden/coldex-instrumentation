from vacuum_instruments import GraphixController
PORT='COM7'
with GraphixController(PORT) as g:
    print('Identity:', g.identify())
    print('CH1:', g.read_pressure(1))
