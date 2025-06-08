# jhs-ac-protocol
 
Results from capturing and analysing the UART protocol used on the internal UART header (labeled WiFi) on JHS manufactured portable air conditioning units. 

So far I haven't been able to send commands to the AC, there must be some sort of control byte I need to set.

For now I've solved this with a custom Home Assistant integration which reads the status message on the Tasmota device connected to the AC, decodes them, and uses the info for the thermostat in the UI, and a second Tasmota device which is an IR blaster which sends the according amounts of IR controll packets to change the temperature, or do any other action. I.e. if the AC-Tasmota device reports "Target temp at 20 Degrees Celsius", Home assistant will reflect this, and if I change the temp in HA to let's say, 16 degrees celsius, Home Assistant will send 4 Temp Down commands through the IR Blaster.

This is the general layout of UART messages sent from the AC over the serial bus:

| Byte | Function/Notes
|------|------------------------------------------------------|
| 0    | Start byte (always 0xA5 in captures)                 |
| 1    | (always 0x00)                                        |
| 2    | (always 0x0D)                                        |
| 3    | Power mode (0x01=on, 0x00=off)                       |
| 4    | Mode (0x01=cool, 0x02=dehum, 0x03=fan)               |
| 5    | Sleep (0x01=sleep, 0x00=normal)                      |
| 6    | Ambient temperature (matches display, C or F)        |
| 7    | Set temperature (user setting or last set)           |
| 8    | Control/protocol (always 0x00)                       |
| 9    | Fan (0x01=low, 0x03=high)                            |
| 10-13| (always 0x00)                                        | 
| 14   | Unit/region (0x20=Celsius, 0x24=Fahrenheit)          |
| 15   | Water tank (0x00=ok, 0x03=full)                      |
| 16   | Checksum (sum bytes 1–15, mod 256)                   |
| 17   | End byte (always 0xF5 in captures)                   |


To send control messages, I've since found out the following, with lots of trial and error, (also before I managed to update this, other people (shoutout to @Lollbrant and @wilkemeyer) have since experimenting and figured this out!)
The following protocol definition can be used: 

| Byte | Function/Notes
|------|------------------------------------------------------|
| 0    | Start byte (always 0xA5)                             |
| 1    | function byte, varies based on function (see below)  |
| 2    | setting, varies based on function (see below)        |
| 3    | copy of setting byte                                 |
| 4    | Checksum                                             |
| 5    | End byte (always 0xF5)                               |


I was able to figure out the following function bytes:

Power:              0x11
Mode:               0x12
Sleep:              0x13
Set temperature:    0x14
Fan speed:          0x16

To interact with these functions, bytes 3 and 4 need to match each other. The following is a table of their possible values:

Power off:                  0x00
Power on:                   0x01

Mode: Cool:                 0x01
      Dehumidify:           0x02
      Fan:                  0x03

For example, setting the AC to fan mode would need the following message: A5 12 03 03 18 F5

Fan speed: Low:             0x01
           High:            0x03

Sleep mode off:             0x00
           on:              0x01


The checksum is calculated exactly the same way as it's done for the heartbeat messages. I've included a hvac.mqtt template for Home Assistant that is able to read heartbeat messages from the AC, as well as send commands to it. 


For celsius, the ambient temperature and set temperature values start at 10. For the set temperature, 10 = 16°C, and increases with the temperature, i.e. 11 = 17°C, 12 = 13°C, etc. These are hex values.

I've made a little jig to connect to AC to an ESP32 flashed with Tasmota. All command attempts were made with SerialSend5. Used a logic level shifter as the AC UART is 5v.

