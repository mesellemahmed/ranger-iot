<?xml version='1.0' encoding='utf-8'?>
<simconf version="2023090101">
  <simulation>
    <title>RANGER UDGM radio-loss k3-n3-rx0.55-seed201</title>
    <randomseed>201</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
org.contikios.cooja.radiomediums.UDGM
<transmitting_range>45.0</transmitting_range>
      <interference_range>70.0</interference_range>
      <success_ratio_tx>1.0</success_ratio_tx>
      <success_ratio_rx>0.550000</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>80000</logoutput>
    </events>
    <motetype>
org.contikios.cooja.contikimote.ContikiMoteType
<description>RANGER Static Coded RPL Mote</description>
      <source>/workspace/experiments/cooja/apps/ranger-static-coded-rpl/ranger-static-coded-rpl.c</source>
      <commands>$(MAKE) -j$(CPUS) ranger-static-coded-rpl.cooja TARGET=cooja DEFINES=RANGER_CODING_K=3,RANGER_CODING_N=3,RANGER_LOSS_BP=0,RANGER_LOSS_SEED=1,RANGER_CAMPAIGN_MODE=0</commands>
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
<pos x="50.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>1</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="85.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>2</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="120.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>3</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="155.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>4</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="190.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>5</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="225.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>6</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="260.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>7</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="295.0" y="100.0" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>8</id>
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
    <bounds x="0" y="0" height="600" width="1000" z="1" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.LogListener
<plugin_config>
      <filter />
      <formatted_time />
      <coloring />
    </plugin_config>
    <bounds x="1000" y="0" height="420" width="800" z="2" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.TimeLine
<plugin_config>
      <mote>0</mote>
      <mote>1</mote>
      <mote>2</mote>
      <mote>3</mote>
      <mote>4</mote>
      <mote>5</mote>
      <mote>6</mote>
      <mote>7</mote>
      <showRadioRXTX>true</showRadioRXTX>
      <showRadioHW>true</showRadioHW>
      <showLEDs>true</showLEDs>
      <showLogOutput>false</showLogOutput>
    </plugin_config>
    <bounds x="0" y="600" height="340" width="1800" z="3" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.RadioLogger
<plugin_config>
      <split>256</split>
      <formatted_time />
      <analyzers name="6lowpan-pcap" />
    </plugin_config>
    <bounds x="1000" y="420" height="180" width="800" z="4" />
  </plugin>
  <plugin>
org.contikios.cooja.plugins.ScriptRunner
<plugin_config>
      <scriptfile>/workspace/experiments/cooja/results/step6c3-radio-loss/campaign-20260928T005420Z-pilot/cases/n3-rx05500-seed000201/assertion.js</scriptfile>
      <active>true</active>
    </plugin_config>
    <bounds x="1000" y="600" height="340" width="800" z="5" />
  </plugin>
</simconf>