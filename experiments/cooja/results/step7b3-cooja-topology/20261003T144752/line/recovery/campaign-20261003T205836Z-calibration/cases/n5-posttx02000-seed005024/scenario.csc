<?xml version='1.0' encoding='utf-8'?>
<simconf version="2023090101">
  <simulation>
    <title>RANGER post-bootstrap stress k3-n5-target-rx0.20-seed5024</title>
    <randomseed>5024</randomseed>
    <motedelay_us>1000000</motedelay_us>
    <radiomedium>
org.contikios.cooja.radiomediums.UDGM
<transmitting_range>45.0</transmitting_range>
      <interference_range>70.0</interference_range>
      <success_ratio_tx>1.000000</success_ratio_tx>
      <success_ratio_rx>1.000000</success_ratio_rx>
    </radiomedium>
    <events>
      <logoutput>80000</logoutput>
    </events>
    <motetype>
org.contikios.cooja.contikimote.ContikiMoteType
<description>RANGER Static Coded RPL Mote</description>
      <source>/workspace/experiments/cooja/apps/ranger-recovery-rpl/ranger-recovery-rpl.c</source>
      <commands>$(MAKE) -j$(CPUS) ranger-recovery-rpl.cooja TARGET=cooja DEFINES=RANGER_CODING_K=3,RANGER_CODING_N=5,RANGER_LOSS_BP=0,RANGER_LOSS_SEED=1,RANGER_CAMPAIGN_MODE=0,RANGER_RECOVERY_SMOKE=0,RANGER_RECOVERY_CASCADE_SMOKE=0</commands>
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
<pos x="135.000000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>1</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="168.750000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>2</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="202.500000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>3</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="236.250000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>4</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="270.000000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>5</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="303.750000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>6</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="337.500000" y="135.000000" />
        </interface_config>
        <interface_config>
org.contikios.cooja.contikimote.interfaces.ContikiMoteID
<id>7</id>
        </interface_config>
      </mote>
      <mote>
        <interface_config>
org.contikios.cooja.interfaces.Position
<pos x="371.250000" y="135.000000" />
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
      <scriptfile>/workspace/experiments/cooja/results/step7b3-cooja-topology/20261003T144752/line/recovery/campaign-20261003T205836Z-calibration/cases/n5-posttx02000-seed005024/assertion.js</scriptfile>
      <active>true</active>
    </plugin_config>
    <bounds x="1000" y="600" height="340" width="800" z="5" />
  </plugin>
</simconf>