# Main Data Collection Pipeline

This package has the components of the main data processing pipeline. It includes three main classes - Sensor, Interpreter, and Writer - that handle the sensing, interpreting, and saving of the instrument data. Data is passed between them with instances of the Bus class when the GUI starts data collection. In `gui.py` you can see how these are all instantiated.

The pipeline is set up in a producer/consumer framework, with methods that only output data (like sensors) as "producers" and those that only receive data (like saving/displaying) as "consumers". There are also "consumer-producers", which read *and* write data. These generally take in sensor data, do some processing, and republish the processed data. This is best visualized in `dummy-sensor-pipeline.py`, which is a bare-bones example of how everything works together with threading.

## Descriptions

### Sensor

### Interpreter

### Writer

### Bus
