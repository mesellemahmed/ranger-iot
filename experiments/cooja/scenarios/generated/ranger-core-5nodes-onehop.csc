<?xml version='1.0' encoding='utf-8'?>
<simconf version="2023090101">
  <simulation>
    <title>RANGER Core — 5 Nodes — One Hop</title>
    <speedlimit>1.0</speedlimit>
    <randomseed>20260925</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
org.contikios.cooja.radiomediums.UDGM
<transmitting_range>50.0</transmitting_range>
      <interference_range>100.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>1.0</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>40000</logoutput>
    </events>
    <motetype>
org.contikios.cooja.contikimote.ContikiMoteType
<description>RANGER Core Mote</description>
      <source>[CONFIG_DIR]/../../apps/ranger-core/ranger-core.c</source>
      <commands>$(MAKE) -j$(CPUS) ranger-core.cooja TARGET=cooja</commands>
      <moteinterface>org.contikios.cooja.interfaces.Position</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Battery</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiVib</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiMoteID</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRS232</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiBeeper</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.IPAddress</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiRadio</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiButton</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiPIR</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiClock</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiLED</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiCFS</moteinterface>
      <moteinterface>org.contikios.cooja.contikimote.interfaces.ContikiEEPROM</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.Mote2MoteRelations</moteinterface>
      <moteinterface>org.contikios.cooja.interfaces.MoteAttributes</moteinterface>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="50.0" y="50.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>1</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="35.0" y="50.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>2</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="65.0" y="50.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>3</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="50.0" y="35.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>4</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="50.0" y="65.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>5</id>
        </interface_config>
      </mote>
    </motetype>
  </simulation>
  <plugin>
org.contikios.cooja.plugins.Visualizer
<plugin_config>
      <moterelations>true</moterelations>
      <skin>org.contikios.cooja.plugins.skins.IDVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.GridVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.TrafficVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.UDGMVisualizerSkin</skin>
      <skin>org.contikios.cooja.plugins.skins.MoteTypeVisualizerSkin</skin>
    </plugin_config>
    <bounds x="0" y="0" height="650" width="850" z="1" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.LogListener
<plugin_config>
      <filter />
      <formatted_time />
      <coloring />
    </plugin_config>
    <bounds x="850" y="0" height="420" width="720" z="2" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.TimeLine
<plugin_config>
      <mote>0</mote>
      <mote>1</mote>
      <mote>2</mote>
      <mote>3</mote>
      <mote>4</mote>
      <showRadioRXTX>true</showRadioRXTX>
      <showRadioHW>true</showRadioHW>
      <showLEDs>true</showLEDs>
      <showLogOutput>false</showLogOutput>
    </plugin_config>
    <bounds x="0" y="650" height="300" width="1570" z="3" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.RadioLogger
<plugin_config>
      <split>256</split>
      <formatted_time />
      <analyzers name="6lowpan-pcap" />
    </plugin_config>
    <bounds x="850" y="420" height="230" width="720" z="4" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.ScriptRunner
<plugin_config>
      <scriptfile>[CONFIG_DIR]/../../tests/ranger-core-assert.js</scriptfile>
      <active>true</active>
    </plugin_config>
    <bounds x="850" y="650" height="300" width="720" z="5" />
  </plugin>
</simconf>