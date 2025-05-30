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

For celsius, the ambient temperature and set temperature values start at 10. For the set temperature, 10 = 16°C, and increases with the temperature, i.e. 11 = 17°C, 12 = 13°C, etc. These are hex values.

I've made a little jig to connect to AC to an ESP32 flashed with Tasmota. All command attempts were made with SerialSend5. Used a logic level shifter as the AC UART is 5v.

