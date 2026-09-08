#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;
const float R_TOP=49900.0f, R_BOTTOM=10000.0f;
const float DIVIDER_GAIN=(R_TOP+R_BOTTOM)/R_BOTTOM; // instrument volts / ADC volts = 5.99
bool streaming=false; float rateHz=10.0f; uint32_t nextSampleUs=0;

void emitSample(){
  uint32_t t=micros();
  Serial.print("{\"type\":\"sample\",\"t_us\":"); Serial.print(t);
  Serial.print(",\"volts\":[");
  for(int ch=0;ch<4;ch++){
    int16_t raw=ads.readADC_SingleEnded(ch);
    float adcV=ads.computeVolts(raw);
    float inputV=adcV*DIVIDER_GAIN;
    if(ch) Serial.print(','); Serial.print(inputV,6);
  }
  Serial.println("]}");
}
void ack(const char* cmd){Serial.print("{\"type\":\"ack\",\"cmd\":\"");Serial.print(cmd);Serial.println("\"}");}
void setup(){
  Serial.begin(115200); delay(500); Wire.begin();
  if(!ads.begin()){Serial.println("{\"type\":\"error\",\"message\":\"ADS1115 not found\"}"); while(1)delay(1000);}
  ads.setGain(GAIN_TWO); // +/-2.048 V full scale, 62.5 uV/bit
  ads.setDataRate(RATE_ADS1115_128SPS);
  Serial.println("{\"type\":\"info\",\"device\":\"adalogger_ads1115\",\"channels\":4,\"divider_gain\":5.99}");
}
void loop(){
  if(Serial.available()){
    String s=Serial.readStringUntil('\n'); s.trim();
    if(s=="READ") emitSample();
    else if(s=="START"){streaming=true; nextSampleUs=micros(); ack("START");}
    else if(s=="STOP"){streaming=false; ack("STOP");}
    else if(s=="PING") Serial.println("{\"type\":\"ack\",\"cmd\":\"PING\"}");
    else if(s=="INFO") Serial.println("{\"type\":\"info\",\"device\":\"adalogger_ads1115\",\"fw\":\"1.0\",\"channels\":4}");
    else if(s.startsWith("RATE ")){float x=s.substring(5).toFloat(); if(x>=0.2 && x<=25){rateHz=x;ack("RATE");}else Serial.println("{\"type\":\"error\",\"message\":\"rate must be 0.2..25 Hz\"}");}
  }
  if(streaming && (int32_t)(micros()-nextSampleUs)>=0){emitSample(); nextSampleUs=micros()+(uint32_t)(1000000.0f/rateHz);}
}
