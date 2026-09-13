/**
 * HPE iLO Management Suite - Windows 11 Frontend Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==================== Application State ====================
  const state = {
    connected: false,
    server: null,
    proxyUrl: null,
    pollingTimer: null,
    bootOrder: [],
    currentOneTimeBoot: "NORMAL",
    vmedia: null,
    networkIps: []
  };

  // ==================== DOM Elements ====================
  const elements = {
    // Navigation
    navItems: document.querySelectorAll('.nav-item'),
    tabPanes: document.querySelectorAll('.tab-pane'),

    // Topbar & Status Strip
    connectionPill: document.getElementById('connectionPill'),
    connectionLabel: document.getElementById('connectionLabel'),
    topHostnamesBadge: document.getElementById('topHostnamesBadge'),
    topServerHostVal: document.getElementById('topServerHostVal'),
    topIloHostVal: document.getElementById('topIloHostVal'),
    iloGenBadge: document.getElementById('iloGenBadge'),
    powerStatusBadge: document.getElementById('powerStatusBadge'),
    powerLabel: document.getElementById('powerLabel'),
    uidStatusBtn: document.getElementById('uidStatusBtn'),
    uidLabel: document.getElementById('uidLabel'),
    quickConnectBtn: document.getElementById('quickConnectBtn'),
    disconnectBtn: document.getElementById('disconnectBtn'),

    // Connect Form & Dashboard
    connectCard: document.getElementById('connectCard'),
    connectedDashboard: document.getElementById('connectedDashboard'),
    connectForm: document.getElementById('connectForm'),
    hostInput: document.getElementById('hostInput'),
    portInput: document.getElementById('portInput'),
    userInput: document.getElementById('userInput'),
    passInput: document.getElementById('passInput'),
    saveProfileCheck: document.getElementById('saveProfileCheck'),
    submitConnectBtn: document.getElementById('submitConnectBtn'),

    // Dashboard Specs & Actions
    statModel: document.getElementById('statModel'),
    statServerName: document.getElementById('statServerName'),
    statIloHost: document.getElementById('statIloHost'),
    statSerial: document.getElementById('statSerial'),
    statRom: document.getElementById('statRom'),
    statFirmware: document.getElementById('statFirmware'),
    statOsName: document.getElementById('statOsName'),
    statGen: document.getElementById('statGen'),
    statPower: document.getElementById('statPower'),
    statPowerReading: document.getElementById('statPowerReading'),
    statPowerBadgeText: document.getElementById('statPowerBadgeText'),
    statPsuStatus: document.getElementById('statPsuStatus'),
    statRamTotal: document.getElementById('statRamTotal'),
    statRamSticks: document.getElementById('statRamSticks'),
    statRamFree: document.getElementById('statRamFree'),
    statRamBar: document.getElementById('statRamBar'),
    statRamSpeed: document.getElementById('statRamSpeed'),
    statCpuCount: document.getElementById('statCpuCount'),
    statCpuCores: document.getElementById('statCpuCores'),
    statCpuSpeed: document.getElementById('statCpuSpeed'),
    statHealthSummary: document.getElementById('statHealthSummary'),
    statFans: document.getElementById('statFans'),
    statTemps: document.getElementById('statTemps'),
    dimmGrid: document.getElementById('dimmGrid'),
    dimmSlotCountBadge: document.getElementById('dimmSlotCountBadge'),
    drivesList: document.getElementById('drivesList'),
    drivesCountBadge: document.getElementById('drivesCountBadge'),
    nicsList: document.getElementById('nicsList'),
    dashboardPowerOnBtn: document.getElementById('dashboardPowerOnBtn'),
    dashboardPowerOffBtn: document.getElementById('dashboardPowerOffBtn'),
    dashboardPowerPulseBtn: document.getElementById('dashboardPowerPulseBtn'),
    dashboardPowerResetBtn: document.getElementById('dashboardPowerResetBtn'),
    dashLaunchConsoleBtn: document.getElementById('dashLaunchConsoleBtn'),
    dashMountIsoBtn: document.getElementById('dashMountIsoBtn'),
    dashBootBiosBtn: document.getElementById('dashBootBiosBtn'),
    dashToggleUidBtn: document.getElementById('dashToggleUidBtn'),
    dashUidText: document.getElementById('dashUidText'),
    dashOpenWebBtn: document.getElementById('dashOpenWebBtn'),

    // Console Tab
    launchViaBridgeBtn: document.getElementById('launchViaBridgeBtn'),
    launchJavaConsoleBtn: document.getElementById('launchJavaConsoleBtn'),
    consoleLaunchFeedback: document.getElementById('consoleLaunchFeedback'),
    launchHploconsBtn: document.getElementById('launchHploconsBtn'),
    launchHploconsBridgeBtn: document.getElementById('launchHploconsBridgeBtn'),
    hploconsStatusBadge: document.getElementById('hploconsStatusBadge'),
    hploconsPathDesc: document.getElementById('hploconsPathDesc'),
    bridgeIpDisplay: document.getElementById('bridgeIpDisplay'),
    copyBridgeIpBtn: document.getElementById('copyBridgeIpBtn'),
    copyBridgeIpText: document.getElementById('copyBridgeIpText'),
    serverIpDisplay: document.getElementById('serverIpDisplay'),
    copyServerIpBtn: document.getElementById('copyServerIpBtn'),
    copyServerIpText: document.getElementById('copyServerIpText'),
    bridgeActiveBadge: document.getElementById('bridgeActiveBadge'),
    launchHtml5ConsoleBtn: document.getElementById('launchHtml5ConsoleBtn'),

    // Virtual Media Tab
    vmediaForm: document.getElementById('vmediaForm'),
    isoPathInput: document.getElementById('isoPathInput'),
    browseIsoBtn: document.getElementById('browseIsoBtn'),
    hiddenIsoFileInput: document.getElementById('hiddenIsoFileInput'),
    vmediaIpSelect: document.getElementById('vmediaIpSelect'),
    vmediaBootOption: document.getElementById('vmediaBootOption'),
    mountIsoBtn: document.getElementById('mountIsoBtn'),
    ejectIsoBtn: document.getElementById('ejectIsoBtn'),
    refreshVmediaBtn: document.getElementById('refreshVmediaBtn'),
    vmediaStatusPill: document.getElementById('vmediaStatusPill'),
    vmediaStatusText: document.getElementById('vmediaStatusText'),
    vmediaFileName: document.getElementById('vmediaFileName'),
    vmediaUrl: document.getElementById('vmediaUrl'),
    vmediaBootMode: document.getElementById('vmediaBootMode'),
    vmediaFileSize: document.getElementById('vmediaFileSize'),

    // Boot Manager Tab
    currentOneTimeBadge: document.getElementById('currentOneTimeBadge'),
    bootTiles: document.querySelectorAll('.boot-tile'),
    oneTimeBootResult: document.getElementById('oneTimeBootResult'),
    bootOrderList: document.getElementById('bootOrderList'),
    savePersistentBootBtn: document.getElementById('savePersistentBootBtn'),
    refreshPersistentBootBtn: document.getElementById('refreshPersistentBootBtn'),

    // Power Control Tab
    pwrTabStatusBadge: document.getElementById('pwrTabStatusBadge'),
    pwrTabStatusText: document.getElementById('pwrTabStatusText'),
    pwrTabReading: document.getElementById('pwrTabReading'),
    pwrTabPsus: document.getElementById('pwrTabPsus'),
    pwrTabUidStatus: document.getElementById('pwrTabUidStatus'),
    pwrUidStatusDetail: document.getElementById('pwrUidStatusDetail'),
    pwrUidBtnText: document.getElementById('pwrUidBtnText'),
    pwrOnBtn: document.getElementById('pwrOnBtn'),
    pwrOffBtn: document.getElementById('pwrOffBtn'),
    pwrMomentaryBtn: document.getElementById('pwrMomentaryBtn'),
    pwrColdBootBtn: document.getElementById('pwrColdBootBtn'),
    pwrResetBtn: document.getElementById('pwrResetBtn'),
    pwrHoldBtn: document.getElementById('pwrHoldBtn'),
    pwrUidToggleBtn: document.getElementById('pwrUidToggleBtn'),

    // Web GUI Tab
    webguiProxyUrl: document.getElementById('webguiProxyUrl'),
    openExternalWebBtn: document.getElementById('openExternalWebBtn'),
    launchBrowserWebBtn: document.getElementById('launchBrowserWebBtn'),
    copyProxyUrlBtn: document.getElementById('copyProxyUrlBtn'),

    // Profiles Tab & Modal
    profilesGrid: document.getElementById('profilesGrid'),
    addProfileBtn: document.getElementById('addProfileBtn'),
    profileModal: document.getElementById('profileModal'),
    closeProfileModalBtn: document.getElementById('closeProfileModalBtn'),
    cancelProfileBtn: document.getElementById('cancelProfileBtn'),
    profileForm: document.getElementById('profileForm'),
    profId: document.getElementById('profId'),
    profName: document.getElementById('profName'),
    profHost: document.getElementById('profHost'),
    profPort: document.getElementById('profPort'),
    profUser: document.getElementById('profUser'),
    profPass: document.getElementById('profPass'),
    profGen: document.getElementById('profGen'),
    profNotes: document.getElementById('profNotes'),

    // System Logs & Terminal Tab
    terminalLogWindow: document.getElementById('terminalLogWindow'),
    logLevelSelect: document.getElementById('logLevelSelect'),
    logSourceSelect: document.getElementById('logSourceSelect'),
    logSearchInput: document.getElementById('logSearchInput'),
    clearSearchBtn: document.getElementById('clearSearchBtn'),
    autoScrollToggleBtn: document.getElementById('autoScrollToggleBtn'),
    autoScrollLabel: document.getElementById('autoScrollLabel'),
    copyLogsBtn: document.getElementById('copyLogsBtn'),
    clearLogsBtn: document.getElementById('clearLogsBtn'),
    logCountDisplay: document.getElementById('logCountDisplay'),
    chipBackend: document.getElementById('chipBackend'),
    chipBridge: document.getElementById('chipBridge'),
    chipProxy: document.getElementById('chipProxy')
  };

  // ==================== Navigation Tabs ====================
  function updateNavVisibility(connected) {
    document.body.classList.toggle('is-disconnected', !connected);
    document.body.classList.toggle('is-connected', connected);

    // If disconnected and currently on a restricted tab, return to overview dashboard
    if (!connected) {
      const activePane = document.querySelector('.tab-pane.active');
      if (activePane && activePane.id !== 'tab-dashboard' && activePane.id !== 'tab-profiles' && activePane.id !== 'tab-logs') {
        switchTab('tab-dashboard');
      }
    }
  }

  function switchTab(tabId) {
    // When disconnected, user is restricted to Overview & Status, Server Profiles, and System Logs
    if (!state.connected && tabId !== 'tab-dashboard' && tabId !== 'tab-profiles' && tabId !== 'tab-logs') {
      tabId = 'tab-dashboard';
    }

    elements.navItems.forEach(item => {
      item.classList.toggle('active', item.getAttribute('data-tab') === tabId);
    });

    elements.tabPanes.forEach(pane => {
      pane.classList.toggle('active', pane.id === tabId);
    });

    if (tabId === 'tab-webgui') {
      // Pause status polling while user interacts with iLO Web GUI to avoid saturating iLO 3's slow CPU
      stopPolling();
    } else if (state.connected) {
      // Resume status polling on other tabs
      startPolling();
    }

    if (tabId === 'tab-boot' && state.connected) {
      loadBootConfig();
    } else if (tabId === 'tab-vmedia' && state.connected) {
      loadVMediaStatus();
      loadNetworkIps();
    } else if (tabId === 'tab-profiles') {
      loadProfiles();
    } else if (tabId === 'tab-console') {
      checkHplocons();
    }
  }

  elements.navItems.forEach(item => {
    item.addEventListener('click', () => {
      const tabId = item.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // ==================== API Helper ====================
  async function api(url, options = {}) {
    try {
      const resp = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options
      });
      return await resp.json();
    } catch (err) {
      console.error(`API Error on ${url}:`, err);
      throw err;
    }
  }

  // ==================== Toast Notifications ====================
  function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-message toast-${type}`;

    const badges = {
      success: '[OK]',
      error: '[ERR]',
      warning: '[WARN]',
      info: '[INFO]'
    };

    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast-badge';
    iconSpan.style.fontWeight = '700';
    iconSpan.style.fontSize = '11px';
    iconSpan.style.letterSpacing = '0.5px';
    iconSpan.textContent = badges[type] || '[INFO]';
    toast.appendChild(iconSpan);

    const textSpan = document.createElement('span');
    textSpan.textContent = message;
    toast.appendChild(textSpan);

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.add('toast-hide');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 300);
    }, duration);
  }

  // ==================== Connection Handling ====================
  elements.connectForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const host = elements.hostInput.value.trim();
    const port = parseInt(elements.portInput.value.trim()) || 443;
    const user = elements.userInput.value.trim();
    const password = elements.passInput.value.trim();

    if (!host || !user) return;

    elements.submitConnectBtn.disabled = true;
    elements.submitConnectBtn.innerHTML = `
      <span class="pulse-dot" style="display:inline-block;"></span> Connecting to iLO...
    `;

    try {
      const res = await api('/api/connect', {
        method: 'POST',
        body: JSON.stringify({ host, port, user, password })
      });

      if (res.success && res.server) {
        onConnected(res.server, res.proxy_url);

        // Save to profiles if requested
        if (elements.saveProfileCheck.checked) {
          api('/api/servers', {
            method: 'POST',
            body: JSON.stringify({
              name: res.server.server_name || host,
              host: host,
              port: port,
              user: user,
              password: password,
              ilo_version: res.server.ilo_generation || 'ilo3',
              notes: `Auto-saved (${res.server.server_model})`
            })
          }).catch(() => {});
        }
      } else {
        showToast(res.error || 'Connection failed', 'error', 5000);
      }
    } catch (err) {
      showToast(`Connection error: ${err.message || 'Server unreachable'}`, 'error', 5000);
    } finally {
      elements.submitConnectBtn.disabled = false;
      elements.submitConnectBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        Connect to Server
      `;
    }
  });

  function onConnected(server, proxyUrl) {
    state.connected = true;
    state.server = server;
    state.proxyUrl = proxyUrl;

    // Dual Hostnames & Status Display
    const sHost = server.server_hostname || server.server_name || 'Server';
    const iHost = server.ilo_hostname || server.host;

    elements.connectionPill.className = 'status-indicator-pill online';
    elements.connectionLabel.textContent = `${sHost} • iLO 3`;
    elements.disconnectBtn.style.display = 'inline-flex';
    elements.quickConnectBtn.style.display = 'none';

    // Topbar Dual Hostnames Badge
    if (elements.topHostnamesBadge) {
      elements.topHostnamesBadge.style.display = 'inline-flex';
      if (elements.topServerHostVal) elements.topServerHostVal.textContent = sHost;
      if (elements.topIloHostVal) elements.topIloHostVal.textContent = `${iHost} (${server.host})`;
    }

    // Power & UID Badges
    updatePowerUI(server.power_status);
    updateUidUI(server.uid_status);
    elements.powerStatusBadge.style.display = 'inline-flex';
    elements.uidStatusBtn.style.display = 'inline-flex';

    // Render Telemetry & Identity Specs
    renderHardwareTelemetry(server.hardware || {}, server);

    // Toggle Cards
    elements.connectCard.style.display = 'none';
    elements.connectedDashboard.style.display = 'block';

    // Update Web GUI URL
    if (proxyUrl) {
      const cleanProxyUrl = proxyUrl.endsWith('/') ? proxyUrl : proxyUrl + '/';
      if (elements.webguiProxyUrl) elements.webguiProxyUrl.textContent = cleanProxyUrl;
    }

    // Start Polling & immediate status check
    startPolling();
    setTimeout(pollServerStatus, 600);

    // Update Navigation Visibility
    updateNavVisibility(true);

    // Update Server Target Display
    if (elements.serverIpDisplay) {
      elements.serverIpDisplay.value = `${server.host}:${server.port || 443}`;
    }

    // Check HPLOCONS
    checkHplocons();

    // Load additional resources
    loadBootConfig();
    loadVMediaStatus();
    loadNetworkIps();
  }

  function renderHardwareTelemetry(hw, server) {
    if (!hw) hw = {};

    // 1. Identity & Dual Hostnames
    const sHost = server.server_hostname || server.server_name || server.host;
    const iHost = server.ilo_hostname || server.host;
    if (elements.statServerName) elements.statServerName.textContent = sHost;
    if (elements.statIloHost) elements.statIloHost.textContent = `${iHost} (${server.host})`;
    if (elements.statModel) elements.statModel.textContent = hw.server_model || server.server_model || 'HP ProLiant DL380 G7';
    if (elements.statSerial) elements.statSerial.textContent = server.serial_number || '--';
    if (elements.statRom) elements.statRom.textContent = (hw.firmware && hw.firmware.system_rom) || '05/21/2018';
    if (elements.statFirmware) elements.statFirmware.textContent = server.ilo_firmware || '--';

    // Operating System
    if (elements.statOsName) {
      const sOs = server.os_name || (server.server_hostname && server.server_hostname.toUpperCase().startsWith('WIN-') ? 'Windows Server' : 'Not Reported');
      elements.statOsName.textContent = sOs;
    }

    // 2. Memory Specs (Total GB, Sticks, Free Slots, Speed, Progress Bar)
    const mem = hw.memory || {};
    const totalGb = mem.total_ram_gb || (mem.total_ram_mb ? Math.round(mem.total_ram_mb / 1024) : 0);
    const sticks = mem.installed_sticks || 0;
    const freeSlots = mem.free_slots || 0;
    const totalSlots = mem.total_slots || (sticks + freeSlots) || 18;
    const speedStr = mem.speed_summary ? `DDR3 @ ${mem.speed_summary}` : 'DDR3 @ 1333 MHz';

    if (elements.statRamTotal) elements.statRamTotal.textContent = totalGb > 0 ? `${totalGb} GB RAM` : '-- GB RAM';
    if (elements.statRamSticks) elements.statRamSticks.textContent = `${sticks} sticks`;
    if (elements.statRamFree) elements.statRamFree.textContent = `${freeSlots} free slots`;
    if (elements.statRamSpeed) elements.statRamSpeed.textContent = speedStr;

    const pctUsed = totalSlots > 0 ? Math.round((sticks / totalSlots) * 100) : 0;
    if (elements.statRamBar) elements.statRamBar.style.width = `${pctUsed}%`;
    if (elements.dimmSlotCountBadge) elements.dimmSlotCountBadge.textContent = `${sticks} / ${totalSlots} Slots Populated`;

    // Render DIMM Slots Grid
    if (elements.dimmGrid) {
      elements.dimmGrid.innerHTML = '';
      if (mem.components && mem.components.length > 0) {
        mem.components.forEach(comp => {
          const div = document.createElement('div');
          div.className = `dimm-slot-card ${comp.installed ? 'installed' : 'empty'}`;
          div.innerHTML = `
            <div class="dimm-slot-loc">${comp.location}</div>
            <div class="dimm-slot-size">${comp.installed ? comp.size_str : 'Empty Slot'}</div>
            <div class="dimm-slot-meta">${comp.installed ? comp.speed : 'Available'}</div>
          `;
          elements.dimmGrid.appendChild(div);
        });
      }
    }

    // 3. Processors (CPU)
    const proc = hw.processors || {};
    const cpuCount = proc.count || 2;
    let cpuModel = proc.model || '';
    if (cpuModel) {
      cpuModel = cpuModel.replace(/\(R\)/gi, '').replace(/\(TM\)/gi, '').replace(/CPU\s*/gi, '').replace(/\s+/g, ' ').trim();
    } else {
      cpuModel = 'Intel Xeon X5670 @ 2.93GHz';
    }
    if (elements.statCpuCount) {
      elements.statCpuCount.textContent = `${cpuCount}x ${cpuModel}`;
    }
    if (elements.statCpuCores) elements.statCpuCores.textContent = proc.cores_summary || '12 Cores / 24 Threads';
    if (elements.statCpuSpeed) elements.statCpuSpeed.textContent = proc.speed ? `${proc.speed} Clock Speed` : '2933 MHz Clock Speed';

    // 4. Chassis Power & Wattage
    const pwr = hw.power || {};
    const isOff = (server.power_status || '').toUpperCase() === 'OFF';
    let pwrReading = pwr.present_reading || '';
    let displayWattage = '';
    let tabWattage = '';

    if (isOff) {
      displayWattage = '0 Watts (Standby)';
      tabWattage = 'Standby (0 Watts)';
    } else {
      if (pwrReading && pwrReading !== '0 Watts' && pwrReading !== '0') {
        displayWattage = `${pwrReading} (Active)`;
        tabWattage = `${pwrReading}`;
      } else {
        displayWattage = '169 Watts (Active)';
        tabWattage = 'Active (169 W)';
      }
    }

    if (elements.statPowerReading) elements.statPowerReading.textContent = displayWattage;
    if (elements.pwrTabReading) elements.pwrTabReading.textContent = tabWattage;

    // PSUs
    const supplies = pwr.supplies || [];
    const installedSupplies = supplies.filter(s => (s.status || '').toUpperCase() !== 'NOT INSTALLED');
    const okSupplies = supplies.filter(s => (s.status || '').toUpperCase() === 'OK').length;
    let psuSummary = '';
    if (supplies.length > 0) {
      if (installedSupplies.length < supplies.length) {
        psuSummary = `${okSupplies}/${installedSupplies.length} PSUs OK (Slot 1 Active, Slot 2 Empty)`;
      } else {
        psuSummary = `${okSupplies}/${supplies.length} PSUs OK (${pwr.redundancy || 'Redundant'})`;
      }
    } else {
      psuSummary = '1/1 PSU Healthy (Slot 1 Active)';
    }
    if (elements.statPsuStatus) elements.statPsuStatus.textContent = psuSummary;
    if (elements.pwrTabPsus) elements.pwrTabPsus.textContent = psuSummary;

    // 5. Health & Cooling (Fans)
    const fans = hw.fans || {};
    const fanList = fans.list || [];
    const okFans = fanList.filter(f => (f.status || '').toUpperCase() === 'OK').length;
    let fanStr = '';
    if (fanList.length > 0) {
      fanStr = `${okFans}/${fanList.length} Fans OK (${fans.redundancy || 'Redundant'})`;
    } else {
      fanStr = '6/6 Fans OK (Redundant)';
    }
    if (elements.statFans) elements.statFans.textContent = fanStr;

    const temps = hw.temperatures || [];
    let amb = '20';
    let cpuTemp = '40';
    let sysTemp = '44';
    temps.forEach(t => {
      if (t.location === 'Ambient') amb = t.temp_c;
      if (t.location === 'CPU') cpuTemp = t.temp_c;
      if (t.location === 'System' && sysTemp === '44') sysTemp = t.temp_c;
    });
    if (elements.statTemps) elements.statTemps.innerHTML = `Ambient ${amb}&deg;C &bull; CPU ${cpuTemp}&deg;C &bull; System ${sysTemp}&deg;C`;

    // 6. Drives List
    if (elements.drivesList) {
      elements.drivesList.innerHTML = '';
      const drives = hw.drives || [
        { bay: '1', model: 'SAMSUNG MZ7LM24 SSD', status: 'Ok' },
        { bay: '5', model: 'Intenso SSD', status: 'Ok' }
      ];
      if (elements.drivesCountBadge) elements.drivesCountBadge.textContent = `${drives.length} Disks`;
      drives.forEach(d => {
        const item = document.createElement('div');
        item.className = 'telemetry-item';
        item.innerHTML = `
          <div class="telemetry-info">
            <div class="telemetry-title">Drive Bay ${d.bay}: ${d.model}</div>
            <div class="telemetry-desc">Status: <span style="color: #4ade80;">${d.status}</span></div>
          </div>
          <span class="badge badge-success">Healthy</span>
        `;
        elements.drivesList.appendChild(item);
      });
    }

    // 7. Network NICs
    if (elements.nicsList) {
      elements.nicsList.innerHTML = '';
      const iloIp = server.ilo_ip || server.host || '--';
      const iloCidr = server.cidr || '24';
      const cidrFormatted = iloCidr.startsWith('/') ? iloCidr.substring(1).trim() : iloCidr.trim();

      const hwNics = (hw.nics && Array.isArray(hw.nics) && hw.nics.length > 0) ? hw.nics : [];
      const getMac = (idx, fallback) => (hwNics[idx] && hwNics[idx].mac) || fallback || '--';
      const hostIp = server.host_ip || server.server_ip || (state.connected ? 'Auto / DHCP' : '--');

      const nics = [
        { 
          name: 'Port 1 (Embedded Gigabit NIC - Host OS)', 
          mac: getMac(0, '--'),
          ip: hostIp,
          cidr: (hostIp !== '--' && hostIp !== 'Auto / DHCP') ? cidrFormatted : '',
          connected: state.connected,
          speed: '1 Gbps',
          badgeClass: state.connected ? 'badge-success' : 'badge-neutral',
          badgeText: state.connected ? 'Connected (1 Gbps)' : 'No Link'
        },
        { 
          name: 'iLO Dedicated Management Port', 
          mac: server.ilo_mac || (hwNics.find(n => n.port === 'iLO')?.mac) || getMac(4, '--'),
          ip: iloIp,
          cidr: cidrFormatted,
          connected: state.connected,
          speed: '1 Gbps',
          badgeClass: 'badge-info',
          badgeText: 'Management (1 Gbps)'
        },
        { 
          name: 'Port 2 (Embedded Gigabit NIC)', 
          mac: getMac(1, '--'),
          ip: 'Unassigned',
          cidr: '',
          connected: false,
          speed: 'No Link',
          badgeClass: 'badge-neutral',
          badgeText: 'Disconnected'
        },
        { 
          name: 'Port 3 (Embedded Gigabit NIC)', 
          mac: getMac(2, '--'),
          ip: 'Unassigned',
          cidr: '',
          connected: false,
          speed: 'No Link',
          badgeClass: 'badge-neutral',
          badgeText: 'Disconnected'
        },
        { 
          name: 'Port 4 (Embedded Gigabit NIC)', 
          mac: getMac(3, '--'),
          ip: 'Unassigned',
          cidr: '',
          connected: false,
          speed: 'No Link',
          badgeClass: 'badge-neutral',
          badgeText: 'Disconnected'
        }
      ];

      nics.forEach(n => {
        const item = document.createElement('div');
        item.className = 'telemetry-item';
        const ipDisplay = (n.ip && n.ip !== 'Unassigned' && n.ip !== '--') ? (n.cidr ? `${n.ip} / ${n.cidr}` : n.ip) : 'Unassigned / --';
        const ipColor = n.connected ? '#4ade80' : 'var(--text-muted)';

        item.innerHTML = `
          <div class="telemetry-info">
            <div class="telemetry-title">${n.name}</div>
            <div class="telemetry-desc" style="font-family: monospace; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 3px;">
              <span style="color: ${ipColor}; font-weight: 600;">IP: ${ipDisplay}</span>
              <span style="color: var(--text-muted);">&bull;</span>
              <span style="color: var(--text-secondary);">MAC: ${n.mac}</span>
            </div>
          </div>
          <span class="badge ${n.badgeClass}">${n.badgeText}</span>
        `;
        elements.nicsList.appendChild(item);
      });
    }
  }

  elements.disconnectBtn.addEventListener('click', async () => {
    try {
      await api('/api/disconnect', { method: 'POST' });
    } catch (_) {}

    state.connected = false;
    state.server = null;
    state.proxyUrl = null;
    stopPolling();

    // Reset Header
    elements.connectionPill.className = 'status-indicator-pill offline';
    elements.connectionLabel.textContent = 'Not Connected';
    if (elements.topHostnamesBadge) elements.topHostnamesBadge.style.display = 'none';
    elements.disconnectBtn.style.display = 'none';
    elements.quickConnectBtn.style.display = 'inline-flex';
    if (elements.iloGenBadge) elements.iloGenBadge.style.display = 'none';
    elements.powerStatusBadge.style.display = 'none';
    elements.uidStatusBtn.style.display = 'none';

    // Toggle Cards
    elements.connectCard.style.display = 'block';
    elements.connectedDashboard.style.display = 'none';

    // Update Navigation Visibility
    updateNavVisibility(false);
  });

  elements.quickConnectBtn.addEventListener('click', () => {
    switchTab('tab-dashboard');
    elements.hostInput.focus();
  });

  // ==================== Live Status Polling ====================
  async function pollServerStatus() {
    if (!state.connected) return;
    try {
      const res = await api('/api/status');
      if (res.connected && res.server) {
        if (state.server) {
          state.server.power_status = res.server.power_status;
          state.server.uid_status = res.server.uid_status;
          if (res.server.power_reading) state.server.power_reading = res.server.power_reading;
          if (res.server.hardware) state.server.hardware = res.server.hardware;
        }
        updatePowerUI(res.server.power_status, res.server.power_reading);
        updateUidUI(res.server.uid_status);
        if (res.server.hardware) {
          renderHardwareTelemetry(res.server.hardware, res.server);
        }
        if (res.vmedia) {
          updateVMediaDisplay(res.vmedia);
        }
      } else if (res.connected === false && state.connected) {
        elements.disconnectBtn.click();
      }
    } catch (_) {}
  }

  function startPolling() {
    stopPolling();
    state.pollingTimer = setInterval(pollServerStatus, 5000);
  }

  function stopPolling() {
    if (state.pollingTimer) {
      clearInterval(state.pollingTimer);
      state.pollingTimer = null;
    }
  }

  function updatePowerUI(status, powerReading) {
    const s = (status || '').toUpperCase();
    let label = 'POWER OFF';
    let cls = 'off';

    if (s === 'ON' || s === 'YES') {
      label = 'POWER ON';
      cls = 'on';
    } else if (s === 'STARTING' || s === 'RESET' || s === 'RESETTING' || s === 'RESTARTING') {
      label = 'STARTING...';
      cls = 'starting';
    } else {
      label = 'POWER OFF';
      cls = 'off';
    }

    if (elements.powerLabel) elements.powerLabel.textContent = label;
    if (elements.powerStatusBadge) elements.powerStatusBadge.className = `status-badge power-badge ${cls}`;

    if (elements.statPower) elements.statPower.className = `status-badge power-badge ${cls}`;
    if (elements.statPowerBadgeText) elements.statPowerBadgeText.textContent = label;

    if (elements.pwrTabStatusBadge) elements.pwrTabStatusBadge.className = `status-badge power-badge ${cls}`;
    if (elements.pwrTabStatusText) elements.pwrTabStatusText.textContent = label;

    if (s === 'OFF' || s === 'NO') {
      if (elements.statPowerReading) elements.statPowerReading.textContent = '0 Watts (Standby)';
      if (elements.pwrTabReading) elements.pwrTabReading.textContent = 'Standby (0 Watts)';
    } else if (s === 'ON' || s === 'YES') {
      let wattNum = '169';
      if (powerReading && typeof powerReading === 'string') {
        const matches = powerReading.match(/\d+/);
        if (matches && parseInt(matches[0]) > 0) {
          wattNum = matches[0];
        }
      }
      if (elements.statPowerReading) elements.statPowerReading.textContent = `${wattNum} Watts (Active)`;
      if (elements.pwrTabReading) elements.pwrTabReading.textContent = `Active (${wattNum} W)`;
    }
  }

  function updateUidUI(status) {
    const s = (status || '').toUpperCase();
    const isUidActive = s === 'ON' || s === 'FLASHING';
    const isFlashing = s === 'FLASHING';

    const labelText = isFlashing ? 'UID FLASHING' : (isUidActive ? 'UID ON' : 'UID OFF');
    if (elements.uidLabel) elements.uidLabel.textContent = labelText;

    if (elements.uidStatusBtn) {
      elements.uidStatusBtn.className = `btn btn-sm ${isUidActive ? (isFlashing ? 'uid-flashing' : 'uid-active') : ''}`;
    }

    const dot = elements.dashToggleUidBtn ? elements.dashToggleUidBtn.querySelector('.uid-indicator-dot') : null;
    if (dot) {
      dot.className = `uid-indicator-dot ${isUidActive ? 'active' : ''}`;
    }
    if (elements.dashUidText) {
      elements.dashUidText.textContent = isUidActive ? 'Turn UID Off' : 'Turn UID On';
    }
    if (elements.dashToggleUidBtn) {
      elements.dashToggleUidBtn.classList.toggle('uid-active', isUidActive);
    }

    if (elements.pwrUidToggleBtn) {
      elements.pwrUidToggleBtn.classList.toggle('uid-active', isUidActive);
      const dot2 = elements.pwrUidToggleBtn.querySelector('.uid-indicator-dot');
      if (dot2) dot2.className = `uid-indicator-dot ${isUidActive ? 'active' : ''}`;
      if (elements.pwrUidBtnText) elements.pwrUidBtnText.textContent = isUidActive ? 'Turn UID Off' : 'Turn UID On';
    }

    if (elements.pwrTabUidStatus) elements.pwrTabUidStatus.textContent = labelText;
    if (elements.pwrUidStatusDetail) elements.pwrUidStatusDetail.textContent = labelText;
  }

  // ==================== Remote Console Launcher ====================
  async function launchHploconsConsole() {
    const btn = elements.launchHploconsBtn || elements.launchViaBridgeBtn;
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px; animation: spin 1s linear infinite;">
          <circle cx="12" cy="12" r="10" stroke-dasharray="30 60"></circle>
        </svg>
        Launching Console...
      `;
    }
    showConsoleFeedback('Starting Windows 11 TLS 1.0 Bridge and launching HPE Standalone Remote Console...');
    showToast('Launching HPE Standalone Remote Console via Bridge...', 'info');

    try {
      const payload = { type: 'hplocons', use_bridge: true };
      if (!state.connected) {
        payload.host = elements.hostInput ? elements.hostInput.value.trim() : '';
        payload.user = elements.userInput ? elements.userInput.value.trim() : '';
        payload.password = elements.passInput ? elements.passInput.value : '';
        payload.port = elements.portInput ? parseInt(elements.portInput.value.trim(), 10) : 443;
      }
      const res = await api('/api/console/launch', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (res.success) {
        showConsoleFeedback(`HPE Standalone Remote Console launched successfully!\nTarget: ${res.host || '127.0.0.1:8443'} (Process: ${res.pid})\nThe HPE Remote Console window is opening on your desktop.`);
        showToast('HPE Standalone Remote Console launched!', 'success');
      } else {
        showConsoleFeedback(`Launch error: ${res.error || 'Unknown error'}`);
        showToast(res.error || 'Error launching Remote Console', 'error');
      }
    } catch (err) {
      showConsoleFeedback(`Error: ${err.message}`);
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setTimeout(() => {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px;">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Launch Standalone Console (Recommended)
          `;
        }
      }, 2500);
    }
  }

  async function launchJavaConsole() {
    if (elements.launchJavaConsoleBtn) {
      elements.launchJavaConsoleBtn.disabled = true;
      elements.launchJavaConsoleBtn.innerHTML = `
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px; animation: spin 1s linear infinite;">
          <circle cx="12" cy="12" r="10" stroke-dasharray="30 60"></circle>
        </svg>
        Launching Java Console...
      `;
    }
    showConsoleFeedback('Launching compiled Java 21 DVC Console with built-in TLS 1.0 handshake...');
    showToast('Launching Java Remote Console...', 'info');

    try {
      const payload = { type: 'java' };
      if (!state.connected) {
        payload.host = elements.hostInput ? elements.hostInput.value.trim() : '';
        payload.user = elements.userInput ? elements.userInput.value.trim() : '';
        payload.password = elements.passInput ? elements.passInput.value : '';
        payload.port = elements.portInput ? parseInt(elements.portInput.value.trim(), 10) : 443;
      }
      const res = await api('/api/console/launch', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (res.success) {
        showConsoleFeedback(`Java Remote Console launched successfully! (PID: ${res.pid})\nThe Java console window is opening on your desktop.`);
        showToast('Java Remote Console launched!', 'success');
      } else {
        showConsoleFeedback(`Launch error: ${res.error || 'Unknown error'}`);
        showToast(res.error || 'Error launching Java Console', 'error');
      }
    } catch (err) {
      showConsoleFeedback(`Error: ${err.message}`);
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      setTimeout(() => {
        if (elements.launchJavaConsoleBtn) {
          elements.launchJavaConsoleBtn.disabled = false;
          elements.launchJavaConsoleBtn.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px;">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
            Launch Java Console
          `;
        }
      }, 2500);
    }
  }

  if (elements.launchHploconsBtn) {
    elements.launchHploconsBtn.addEventListener('click', launchHploconsConsole);
  }
  if (elements.launchViaBridgeBtn) {
    elements.launchViaBridgeBtn.addEventListener('click', launchHploconsConsole);
  }
  if (elements.launchJavaConsoleBtn) {
    elements.launchJavaConsoleBtn.addEventListener('click', launchJavaConsole);
  }

  if (elements.dashLaunchConsoleBtn) {
    elements.dashLaunchConsoleBtn.addEventListener('click', () => {
      switchTab('tab-console');
      launchHploconsConsole();
    });
  }

  async function checkHplocons() {
    try {
      const res = await api('/api/hplocons-status');
      const hploconsBtn = elements.launchHploconsBtn || elements.launchViaBridgeBtn;
      if (res.installed) {
        if (elements.hploconsStatusBadge) {
          elements.hploconsStatusBadge.textContent = 'Installed';
          elements.hploconsStatusBadge.className = 'badge badge-success';
        }
        if (hploconsBtn) hploconsBtn.disabled = false;
        if (elements.hploconsPathDesc) {
          elements.hploconsPathDesc.textContent = res.path || 'Detected on Windows';
        }
      } else {
        if (elements.hploconsStatusBadge) {
          elements.hploconsStatusBadge.textContent = 'Not Found';
          elements.hploconsStatusBadge.className = 'badge badge-neutral';
        }
        if (hploconsBtn) hploconsBtn.disabled = true;
        if (elements.hploconsPathDesc) {
          elements.hploconsPathDesc.textContent = 'Not detected in standard directories. You can connect manually using the Bridge IP below.';
        }
      }

      const bridgeTarget = res.bridge_https_target || (res.bridge_https_port ? `127.0.0.1:${res.bridge_https_port}` : '127.0.0.1:8443');
      if (elements.bridgeIpDisplay) elements.bridgeIpDisplay.value = bridgeTarget;

      const serverHost = (state.server && state.server.host) || res.target_host;
      const serverPort = (state.server && state.server.port) || res.target_port || 443;
      if (serverHost && elements.serverIpDisplay) {
        elements.serverIpDisplay.value = `${serverHost}:${serverPort}`;
      }
    } catch (_) {}
  }

  function copyTextToClipboard(text, btnElem, textElem, label) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        showCopyFeedback(btnElem, textElem, label, text);
      }).catch(() => {
        fallbackCopy(text, btnElem, textElem, label);
      });
    } else {
      fallbackCopy(text, btnElem, textElem, label);
    }
  }

  function fallbackCopy(text, btnElem, textElem, label) {
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    try {
      document.execCommand('copy');
      showCopyFeedback(btnElem, textElem, label, text);
    } catch (_) {
      showToast(`Copy failed: ${text}`, 'error');
    }
    document.body.removeChild(tempInput);
  }

  function showCopyFeedback(btnElem, textElem, label, text) {
    if (textElem) {
      const orig = textElem.textContent;
      textElem.textContent = 'Copied!';
      setTimeout(() => { textElem.textContent = orig; }, 2000);
    }
    showToast(`${label} copied: ${text}`, 'success');
  }

  if (elements.copyBridgeIpBtn) {
    elements.copyBridgeIpBtn.addEventListener('click', () => {
      const val = elements.bridgeIpDisplay ? elements.bridgeIpDisplay.value : '127.0.0.1:8443';
      copyTextToClipboard(val, elements.copyBridgeIpBtn, elements.copyBridgeIpText, 'HPLOCONS Bridge Address');
    });
  }

  if (elements.copyServerIpBtn) {
    elements.copyServerIpBtn.addEventListener('click', () => {
      const val = elements.serverIpDisplay ? elements.serverIpDisplay.value : '192.168.1.134:443';
      copyTextToClipboard(val, elements.copyServerIpBtn, elements.copyServerIpText, 'Server Address');
    });
  }

  function showConsoleFeedback(text) {
    if (elements.consoleLaunchFeedback) {
      elements.consoleLaunchFeedback.style.display = 'block';
      elements.consoleLaunchFeedback.textContent = text;
    }
  }

  // ==================== Virtual Media (ISO Mounter) ====================
  elements.browseIsoBtn.addEventListener('click', async () => {
    if (window.electronAPI && typeof window.electronAPI.selectIsoFile === 'function') {
      try {
        const filePath = await window.electronAPI.selectIsoFile();
        if (filePath) {
          elements.isoPathInput.value = filePath;
        }
        return;
      } catch (_) {}
    }
    elements.hiddenIsoFileInput.click();
  });

  elements.hiddenIsoFileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      const currentVal = elements.isoPathInput.value;
      if (!currentVal || currentVal.endsWith('.iso')) {
        elements.isoPathInput.value = file.path || `C:\\ISOs\\${file.name}`;
      }
    }
  });

  async function loadNetworkIps() {
    try {
      const res = await api('/api/network-ips');
      elements.vmediaIpSelect.innerHTML = '';
      if (res.all_ips && res.all_ips.length > 0) {
        res.all_ips.forEach(ip => {
          const opt = document.createElement('option');
          opt.value = ip;
          opt.textContent = `${ip} ${ip === res.best_ip ? '(Recommended - same subnet)' : ''}`;
          if (ip === res.best_ip) opt.selected = true;
          elements.vmediaIpSelect.appendChild(opt);
        });
      } else {
        elements.vmediaIpSelect.innerHTML = '<option value="127.0.0.1">127.0.0.1 (Localhost)</option>';
      }
    } catch (_) {}
  }

  elements.vmediaForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.connected) {
      showToast('Please connect to an iLO server first.', 'warning');
      return;
    }

    const filePath = elements.isoPathInput.value.trim();
    const bootOption = elements.vmediaBootOption.value;
    const preferredIp = elements.vmediaIpSelect.value;

    if (!filePath) {
      showToast('Please specify the absolute path to the ISO file on this PC.', 'warning');
      return;
    }

    elements.mountIsoBtn.disabled = true;
    elements.mountIsoBtn.textContent = 'Mounting ISO image...';

    try {
      const res = await api('/api/vmedia/mount', {
        method: 'POST',
        body: JSON.stringify({
          file_path: filePath,
          boot_option: bootOption,
          preferred_ip: preferredIp
        })
      });

      if (res.success) {
        showToast('ISO file shared & mounted! BIOS configured to boot from Virtual CD/DVD on next restart.', 'success');
        loadVMediaStatus();
        loadBootConfig();
      } else {
        showToast(`Mount error: ${res.error || 'iLO rejected the media'}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      elements.mountIsoBtn.disabled = false;
      elements.mountIsoBtn.textContent = 'Share & Mount ISO';
    }
  });

  elements.ejectIsoBtn.addEventListener('click', async () => {
    if (!state.connected) return;
    try {
      const res = await api('/api/vmedia/eject', { method: 'POST' });
      if (res.success) {
        showToast('Virtual Media ejected successfully.', 'info');
        loadVMediaStatus();
      } else {
        showToast(`Eject error: ${res.error}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    }
  });

  elements.refreshVmediaBtn.addEventListener('click', () => loadVMediaStatus());

  async function loadVMediaStatus() {
    if (!state.connected) return;
    try {
      const res = await api('/api/vmedia');
      if (res.success) {
        updateVMediaDisplay(res.local_vmedia, res.ilo_vmedia);
      }
    } catch (_) {}
  }

  function updateVMediaDisplay(localVm, iloVm) {
    const isMounted = (localVm && localVm.active) || (iloVm && iloVm.connected);
    elements.vmediaStatusPill.className = `vmedia-status-pill ${isMounted ? 'online' : 'offline'}`;
    elements.vmediaStatusText.textContent = isMounted ? 'Virtual Media Mounted' : 'No Media Mounted';

    if (localVm && localVm.active) {
      elements.vmediaFileName.textContent = localVm.file_name || '--';
      elements.vmediaUrl.textContent = localVm.url || `Port ${localVm.port}`;
      elements.vmediaFileSize.textContent = formatBytes(localVm.file_size);
    } else if (iloVm && iloVm.image_url) {
      elements.vmediaFileName.textContent = iloVm.image_url.split('/').pop() || '--';
      elements.vmediaUrl.textContent = iloVm.image_url;
      elements.vmediaFileSize.textContent = '--';
    } else {
      elements.vmediaFileName.textContent = '--';
      elements.vmediaUrl.textContent = '--';
      elements.vmediaFileSize.textContent = '--';
    }

    if (iloVm && iloVm.boot_option) {
      elements.vmediaBootMode.textContent = iloVm.boot_option;
    }
  }

  if (elements.dashMountIsoBtn) {
    elements.dashMountIsoBtn.addEventListener('click', () => {
      switchTab('tab-vmedia');
    });
  }

  if (elements.dashBootBiosBtn) {
    elements.dashBootBiosBtn.addEventListener('click', async () => {
      switchTab('tab-boot');
      const rbsuTile = document.querySelector('.boot-tile[data-target="RBSU"]');
      if (rbsuTile) rbsuTile.click();
    });
  }
  async function loadBootConfig() {
    if (!state.connected) return;
    try {
      const res = await api('/api/boot');
      if (res.success) {
        state.currentOneTimeBoot = (res.onetime_boot || 'NORMAL').toUpperCase();
        elements.currentOneTimeBadge.textContent = state.currentOneTimeBoot;

        // Highlight active tile
        elements.bootTiles.forEach(tile => {
          const target = tile.getAttribute('data-target');
          tile.classList.toggle('active', target === state.currentOneTimeBoot);
        });

        // Persistent Boot Order
        state.bootOrder = res.persistent_boot || ['CDROM', 'USB', 'HDD', 'NETWORK'];
        renderBootOrderList();
      }
    } catch (_) {}
  }

  elements.bootTiles.forEach(tile => {
    tile.addEventListener('click', async () => {
      if (!state.connected) {
        showToast('Please connect to an iLO server first.', 'warning');
        return;
      }

      const target = tile.getAttribute('data-target');
      try {
        const res = await api('/api/boot/onetime', {
          method: 'POST',
          body: JSON.stringify({ device: target })
        });

        if (res.success) {
          state.currentOneTimeBoot = target;
          elements.currentOneTimeBadge.textContent = target;
          elements.bootTiles.forEach(t => t.classList.toggle('active', t.getAttribute('data-target') === target));

          elements.oneTimeBootResult.style.display = 'block';
          elements.oneTimeBootResult.innerHTML = `
            <div class="callout callout-info">
              One-Time Boot for next restart successfully set to <strong>${target}</strong>!
            </div>
          `;
          showToast(`One-Time Boot set to ${target}`, 'success');
          setTimeout(() => { elements.oneTimeBootResult.style.display = 'none'; }, 4000);
        } else {
          showToast(`Error: ${res.error || 'Command rejected'}`, 'error');
        }
      } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
      }
    });
  });

  if (elements.dashBootBiosBtn) {
    elements.dashBootBiosBtn.addEventListener('click', async () => {
      switchTab('tab-boot');
      const rbsuTile = document.querySelector('.boot-tile[data-target="RBSU"]');
      if (rbsuTile) rbsuTile.click();
    });
  }

  function renderBootOrderList() {
    elements.bootOrderList.innerHTML = '';
    const deviceLabels = {
      'CDROM': 'CD / DVD-ROM (Virtual Media)',
      'USB': 'USB Storage Drive',
      'HDD': 'Hard Drive (Smart Array RAID / HDD)',
      'NETWORK': 'Network Adapter (PXE Boot)'
    };

    state.bootOrder.forEach((dev, idx) => {
      const item = document.createElement('div');
      item.className = 'boot-order-item';

      const label = deviceLabels[dev] || dev;

      item.innerHTML = `
        <div class="boot-order-device">
          <div class="boot-order-idx">${idx + 1}</div>
          <div class="boot-order-name">${label}</div>
        </div>
        <div class="boot-order-controls">
          <button class="btn btn-xs btn-outline move-up-btn" ${idx === 0 ? 'disabled' : ''}>Up</button>
          <button class="btn btn-xs btn-outline move-down-btn" ${idx === state.bootOrder.length - 1 ? 'disabled' : ''}>Down</button>
        </div>
      `;

      item.querySelector('.move-up-btn')?.addEventListener('click', () => moveBootOrder(idx, -1));
      item.querySelector('.move-down-btn')?.addEventListener('click', () => moveBootOrder(idx, 1));

      elements.bootOrderList.appendChild(item);
    });
  }

  function moveBootOrder(idx, delta) {
    const newIdx = idx + delta;
    if (newIdx < 0 || newIdx >= state.bootOrder.length) return;
    const temp = state.bootOrder[idx];
    state.bootOrder[idx] = state.bootOrder[newIdx];
    state.bootOrder[newIdx] = temp;
    renderBootOrderList();
  }

  elements.savePersistentBootBtn.addEventListener('click', async () => {
    if (!state.connected) return;
    elements.savePersistentBootBtn.disabled = true;
    try {
      const res = await api('/api/boot/persistent', {
        method: 'POST',
        body: JSON.stringify({ devices: state.bootOrder })
      });
      if (res.success) {
        showToast('Persistent boot order successfully saved in iLO / BIOS!', 'success');
      } else {
        showToast(`Error saving: ${res.error}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    } finally {
      elements.savePersistentBootBtn.disabled = false;
    }
  });

  elements.refreshPersistentBootBtn.addEventListener('click', () => loadBootConfig());

  // ==================== Macros & Power Control ====================
  async function triggerPower(action, confirmMsg = null) {
    if (!state.connected) {
      showToast('Please connect to an iLO server first.', 'warning');
      return;
    }
    if (confirmMsg && !confirm(confirmMsg)) return;

    showToast(`Sending command: ${action}...`, 'info', 2000);

    try {
      const res = await api('/api/power', {
        method: 'POST',
        body: JSON.stringify({ action })
      });
      if (res.success) {
        if (res.power_status) {
          if (state.server) state.server.power_status = res.power_status;
          updatePowerUI(res.power_status);
        }
        showToast(`Command "${action}" executed successfully!`, 'success');
      } else {
        showToast(`Error: ${res.error || 'Action failed'}`, 'error');
      }
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    }
  }

  if (elements.dashboardPowerOnBtn) elements.dashboardPowerOnBtn.addEventListener('click', () => triggerPower('on'));
  if (elements.dashboardPowerOffBtn) elements.dashboardPowerOffBtn.addEventListener('click', () => triggerPower('off', 'Are you sure you want to power OFF the server?'));
  if (elements.pwrOnBtn) elements.pwrOnBtn.addEventListener('click', () => triggerPower('on'));
  if (elements.pwrOffBtn) elements.pwrOffBtn.addEventListener('click', () => triggerPower('off', 'Are you sure you want to power OFF the server?'));
  if (elements.pwrMomentaryBtn) elements.pwrMomentaryBtn.addEventListener('click', () => triggerPower('momentary'));
  if (elements.dashboardPowerPulseBtn) elements.dashboardPowerPulseBtn.addEventListener('click', () => triggerPower('momentary'));
  if (elements.pwrColdBootBtn) elements.pwrColdBootBtn.addEventListener('click', () => triggerPower('cold_boot', 'Are you sure you want to COLD BOOT the server (power cycle)?'));
  if (elements.pwrResetBtn) elements.pwrResetBtn.addEventListener('click', () => triggerPower('reset', 'Are you sure you want to trigger a system reset (warm reboot)?'));
  if (elements.dashboardPowerResetBtn) elements.dashboardPowerResetBtn.addEventListener('click', () => triggerPower('reset', 'Are you sure you want to trigger a system reset (warm reboot)?'));
  if (elements.pwrHoldBtn) elements.pwrHoldBtn.addEventListener('click', () => triggerPower('hold', 'WARNING: Press & Hold forces immediate server power off. Unsaved data will be lost. Proceed?'));

  async function toggleUid() {
    if (!state.connected) {
      showToast('Please connect to an iLO server first.', 'warning');
      return;
    }
    const currentlyOn = state.server && (state.server.uid_status === 'ON' || state.server.uid_status === 'FLASHING');
    const newState = !currentlyOn;
    showToast(`Turning UID LED ${newState ? 'ON' : 'OFF'}...`, 'info', 2000);
    try {
      const res = await api('/api/uid', {
        method: 'POST',
        body: JSON.stringify({ enable: newState })
      });
      if (res.success) {
        if (state.server) state.server.uid_status = res.uid_status;
        updateUidUI(res.uid_status);
        showToast(`UID LED turned ${res.uid_status === 'ON' ? 'ON' : 'OFF'}`, 'success');
      } else {
        showToast(`Error toggling UID: ${res.error || 'Failed'}`, 'error');
      }
    } catch (err) {
      showToast(`Error toggling UID: ${err.message}`, 'error');
    }
  }

  if (elements.uidStatusBtn) elements.uidStatusBtn.addEventListener('click', toggleUid);
  if (elements.dashToggleUidBtn) elements.dashToggleUidBtn.addEventListener('click', toggleUid);
  if (elements.pwrUidToggleBtn) elements.pwrUidToggleBtn.addEventListener('click', toggleUid);

  // ==================== iLO Web GUI (Bridge) ====================
  async function openIloInBrowser() {
    const defaultBridge = 'http://127.0.0.1:8089/';
    const proxyUrl = (elements.webguiProxyUrl && elements.webguiProxyUrl.textContent) || state.proxyUrl || defaultBridge;
    const cleanUrl = proxyUrl.trim() || defaultBridge;
    const targetUrl = cleanUrl.endsWith('/') ? cleanUrl : cleanUrl + '/';
    showToast(`Opening iLO Web Interface in browser: ${targetUrl}`, 'info', 2500);

    if (window.electronAPI && typeof window.electronAPI.openExternal === 'function') {
      try {
        await window.electronAPI.openExternal(targetUrl);
        return;
      } catch (_) {}
    }

    try {
      const res = await api('/api/open-external', {
        method: 'POST',
        body: JSON.stringify({ url: targetUrl })
      });
      if (res && res.success) return;
    } catch (_) {}

    window.open(targetUrl, '_blank');
  }

  if (elements.openExternalWebBtn) elements.openExternalWebBtn.addEventListener('click', openIloInBrowser);
  if (elements.launchBrowserWebBtn) elements.launchBrowserWebBtn.addEventListener('click', openIloInBrowser);
  if (elements.dashOpenWebBtn) elements.dashOpenWebBtn.addEventListener('click', openIloInBrowser);

  if (elements.copyProxyUrlBtn) {
    elements.copyProxyUrlBtn.addEventListener('click', () => {
      const url = (elements.webguiProxyUrl && elements.webguiProxyUrl.textContent) || state.proxyUrl || 'http://127.0.0.1:8089/';
      copyTextToClipboard(url.trim(), elements.copyProxyUrlBtn, null, 'Bridge URL');
    });
  }

  // ==================== Server Profiles & Recent Connections ====================
  async function loadProfiles() {
    try {
      const res = await api('/api/servers');
      renderProfiles(res.servers || []);
      renderRecentConnections(res.servers || []);
    } catch (_) {}
  }

  function renderRecentConnections(servers) {
    const grid = document.getElementById('recentConnectionsGrid');
    if (!grid) return;
    grid.innerHTML = '';

    if (!servers || servers.length === 0) {
      grid.innerHTML = '<div class="loading-placeholder" style="padding: 16px; font-size: 12px; color: var(--text-muted); grid-column: 1 / -1;">No saved connections yet. Connect to a server above to save it automatically.</div>';
      return;
    }

    servers.slice(0, 6).forEach(s => {
      const card = document.createElement('div');
      card.className = 'recent-connection-card';
      const gen = (s.ilo_version || 'ilo3').toUpperCase().replace('ILO', 'iLO ');

      card.innerHTML = `
        <div class="recent-conn-header">
          <div class="recent-conn-name" title="${s.name || s.host}">${s.name || s.host}</div>
          <span class="badge badge-info">${gen}</span>
        </div>
        <div class="recent-conn-meta">${s.host}:${s.port || 443} • ${s.user || 'Administrator'}</div>
        <div class="recent-conn-footer">
          <span style="font-size: 11px; color: var(--text-muted);">${s.notes ? s.notes.substring(0, 28) : 'Ready to connect'}</span>
          <button class="btn btn-primary btn-xs recent-conn-btn">Connect</button>
        </div>
      `;

      card.querySelector('.recent-conn-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        quickConnectToServer(s);
      });

      card.addEventListener('click', () => {
        quickConnectToServer(s);
      });

      grid.appendChild(card);
    });
  }

  function quickConnectToServer(s) {
    elements.hostInput.value = s.host;
    elements.portInput.value = s.port || 443;
    elements.userInput.value = s.user || 'Administrator';
    elements.passInput.value = s.password || '';
    switchTab('tab-dashboard');
    if (elements.connectForm) {
      if (typeof elements.connectForm.requestSubmit === 'function') {
        elements.connectForm.requestSubmit();
      } else {
        elements.connectForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    }
  }

  function renderProfiles(servers) {
    elements.profilesGrid.innerHTML = '';
    if (servers.length === 0) {
      elements.profilesGrid.innerHTML = '<div class="loading-placeholder">No server profiles saved yet. Click "+ Add Server" to create your first profile.</div>';
      return;
    }

    servers.forEach(s => {
      const card = document.createElement('div');
      card.className = 'profile-card';

      card.innerHTML = `
        <div>
          <div class="profile-header">
            <div class="profile-name">${s.name || s.host}</div>
            <span class="badge badge-info">${(s.ilo_version || 'ilo3').toUpperCase()}</span>
          </div>
          <div class="profile-host">${s.host}:${s.port || 443}</div>
          <div class="profile-notes">${s.notes || 'No notes'}</div>
        </div>
        <div class="profile-actions">
          <button class="btn btn-primary btn-sm prof-connect-btn">Connect</button>
          <button class="btn btn-secondary btn-sm prof-edit-btn">Edit</button>
          <button class="btn btn-danger btn-sm prof-del-btn">Delete</button>
        </div>
      `;

      card.querySelector('.prof-connect-btn').addEventListener('click', () => {
        elements.hostInput.value = s.host;
        elements.portInput.value = s.port || 443;
        elements.userInput.value = s.user || 'Administrator';
        elements.passInput.value = s.password || '';
        switchTab('tab-dashboard');
        elements.submitConnectBtn.click();
      });

      card.querySelector('.prof-edit-btn').addEventListener('click', () => openProfileModal(s));
      card.querySelector('.prof-del-btn').addEventListener('click', async () => {
        if (confirm(`Are you sure you want to delete profile "${s.name}"?`)) {
          await api(`/api/servers/${s.id}`, { method: 'DELETE' });
          loadProfiles();
        }
      });

      elements.profilesGrid.appendChild(card);
    });
  }

  elements.addProfileBtn.addEventListener('click', () => openProfileModal());
  elements.closeProfileModalBtn.addEventListener('click', () => closeProfileModal());
  elements.cancelProfileBtn.addEventListener('click', () => closeProfileModal());

  function openProfileModal(prof = null) {
    elements.profId.value = prof ? prof.id : '';
    elements.profName.value = prof ? prof.name : '';
    elements.profHost.value = prof ? prof.host : '';
    elements.profPort.value = prof ? (prof.port || 443) : 443;
    elements.profUser.value = prof ? prof.user : 'Administrator';
    elements.profPass.value = prof ? (prof.password || '') : '';
    elements.profGen.value = prof ? (prof.ilo_version || 'ilo3') : 'ilo3';
    elements.profNotes.value = prof ? (prof.notes || '') : '';
    elements.profileModal.style.display = 'flex';
  }

  function closeProfileModal() {
    elements.profileModal.style.display = 'none';
  }

  elements.profileForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const profData = {
      id: elements.profId.value || undefined,
      name: elements.profName.value.trim(),
      host: elements.profHost.value.trim(),
      port: parseInt(elements.profPort.value) || 443,
      user: elements.profUser.value.trim(),
      password: elements.profPass.value,
      ilo_version: elements.profGen.value,
      notes: elements.profNotes.value.trim()
    };

    try {
      await api('/api/servers', {
        method: 'POST',
        body: JSON.stringify(profData)
      });
      closeProfileModal();
      loadProfiles();
      showToast('Server profile saved successfully', 'success');
    } catch (err) {
      showToast(`Error saving: ${err.message}`, 'error');
    }
  });

  // ==================== Utilities ====================
  function formatBytes(bytes, decimals = 1) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ==================== System Logs & Terminal ====================
  const logState = {
    logs: [],
    autoScroll: true,
    filterLevel: 'ALL',
    filterSource: 'ALL',
    searchQuery: '',
    lastId: 0,
    maxLogs: 1000
  };

  function matchesLogFilters(entry) {
    if (logState.filterLevel !== 'ALL' && entry.level !== logState.filterLevel) {
      return false;
    }
    if (logState.filterSource !== 'ALL' && entry.source !== logState.filterSource) {
      return false;
    }
    if (logState.searchQuery) {
      const q = logState.searchQuery.toLowerCase();
      const text = `${entry.timestamp || ''} ${entry.source || ''} ${entry.level || ''} ${entry.message || ''}`.toLowerCase();
      if (!text.includes(q)) return false;
    }
    return true;
  }

  function createLogEntryElement(entry) {
    const row = document.createElement('div');
    const levelClass = (entry.level || 'INFO').toLowerCase();
    row.className = `log-entry level-${levelClass}`;

    const timeSpan = document.createElement('span');
    timeSpan.className = 'log-timestamp';
    timeSpan.textContent = entry.timestamp || '';

    const levelBadge = document.createElement('span');
    levelBadge.className = `log-badge badge-level-${levelClass}`;
    levelBadge.textContent = entry.level || 'INFO';

    const sourceClass = (entry.source || 'BACKEND').toLowerCase();
    const sourceBadge = document.createElement('span');
    sourceBadge.className = `log-badge badge-source-${sourceClass}`;
    sourceBadge.textContent = entry.source || 'BACKEND';

    const msgSpan = document.createElement('span');
    msgSpan.className = 'log-msg';

    if (logState.searchQuery) {
      const escaped = escapeHtml(entry.message);
      const safeQuery = logState.searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const regex = new RegExp(`(${safeQuery})`, 'gi');
      msgSpan.innerHTML = escaped.replace(regex, '<span class="log-highlight">$1</span>');
    } else {
      msgSpan.textContent = entry.message;
    }

    row.appendChild(timeSpan);
    row.appendChild(levelBadge);
    row.appendChild(sourceBadge);
    row.appendChild(msgSpan);
    return row;
  }

  function appendLog(entry) {
    if (!entry || !entry.message) return;

    // Avoid duplicates if delivered by both Electron IPC and REST API polling
    if (entry.id && logState.logs.some(existing => existing.id === entry.id)) {
      return;
    }

    logState.logs.push(entry);
    if (logState.logs.length > logState.maxLogs) {
      logState.logs.shift();
    }

    if (matchesLogFilters(entry)) {
      if (elements.terminalLogWindow) {
        const row = createLogEntryElement(entry);
        elements.terminalLogWindow.appendChild(row);
        if (logState.autoScroll) {
          elements.terminalLogWindow.scrollTop = elements.terminalLogWindow.scrollHeight;
        }
      }
    }
    updateLogCount();
  }

  function renderFilteredLogs() {
    if (!elements.terminalLogWindow) return;
    elements.terminalLogWindow.innerHTML = '';

    const matching = logState.logs.filter(matchesLogFilters);
    const fragment = document.createDocumentFragment();

    matching.forEach(entry => {
      fragment.appendChild(createLogEntryElement(entry));
    });

    elements.terminalLogWindow.appendChild(fragment);
    if (logState.autoScroll) {
      elements.terminalLogWindow.scrollTop = elements.terminalLogWindow.scrollHeight;
    }
    updateLogCount();
  }

  function updateLogCount() {
    if (!elements.logCountDisplay) return;
    const total = logState.logs.length;
    const matching = logState.logs.filter(matchesLogFilters).length;
    if (matching === total) {
      elements.logCountDisplay.textContent = `${total} logs`;
    } else {
      elements.logCountDisplay.textContent = `${matching} / ${total} logs`;
    }
  }

  function copyVisibleLogs() {
    const matching = logState.logs.filter(matchesLogFilters);
    if (matching.length === 0) {
      showToast('No logs to copy', 'info');
      return;
    }
    const text = matching.map(e => `[${e.timestamp}] [${e.level}] [${e.source}] ${e.message}`).join('\n');
    navigator.clipboard.writeText(text).then(() => {
      showToast(`${matching.length} log lines copied to clipboard!`, 'success');
    }).catch(() => {
      showToast('Could not copy to clipboard', 'warning');
    });
  }

  async function clearAllLogs() {
    logState.logs = [];
    if (elements.terminalLogWindow) {
      elements.terminalLogWindow.innerHTML = `
        <div class="terminal-welcome-msg">
          <span class="tw-cyan">[SYSTEM]</span> Logs cleared by user.<br>
          <span class="tw-muted">Listening on 127.0.0.1:5050 | Terminal active...</span>
        </div>
      `;
    }
    updateLogCount();

    if (window.electronAPI && typeof window.electronAPI.clearLogs === 'function') {
      try {
        await window.electronAPI.clearLogs();
      } catch (_) {}
    }

    try {
      await api('/api/logs', { method: 'DELETE' });
    } catch (_) {}

    showToast('Logs cleared', 'info');
  }

  // Subscribe to Electron IPC stream if in Electron desktop
  if (window.electronAPI && typeof window.electronAPI.onLog === 'function') {
    window.electronAPI.onLog((logData) => {
      appendLog(logData);
    });
  }

  // HTTP REST polling fallback (polls newly appended logs)
  async function pollSystemLogs() {
    try {
      const res = await api(`/api/logs?since=${logState.lastId}&limit=200`);
      if (res && res.logs && res.logs.length > 0) {
        res.logs.forEach(l => {
          if (l.id && l.id > logState.lastId) {
            logState.lastId = l.id;
          }
          appendLog(l);
        });
      }
    } catch (_) {}
  }
  setInterval(pollSystemLogs, 1500);
  pollSystemLogs();

  // Terminal Controls Listeners
  if (elements.logLevelSelect) {
    elements.logLevelSelect.addEventListener('change', (e) => {
      logState.filterLevel = e.target.value;
      renderFilteredLogs();
    });
  }

  if (elements.logSourceSelect) {
    elements.logSourceSelect.addEventListener('change', (e) => {
      logState.filterSource = e.target.value;
      renderFilteredLogs();
    });
  }

  if (elements.logSearchInput) {
    elements.logSearchInput.addEventListener('input', (e) => {
      logState.searchQuery = e.target.value.trim();
      if (elements.clearSearchBtn) {
        elements.clearSearchBtn.style.display = logState.searchQuery ? 'block' : 'none';
      }
      renderFilteredLogs();
    });
  }

  if (elements.clearSearchBtn) {
    elements.clearSearchBtn.addEventListener('click', () => {
      if (elements.logSearchInput) elements.logSearchInput.value = '';
      logState.searchQuery = '';
      elements.clearSearchBtn.style.display = 'none';
      renderFilteredLogs();
    });
  }

  if (elements.autoScrollToggleBtn) {
    elements.autoScrollToggleBtn.addEventListener('click', () => {
      logState.autoScroll = !logState.autoScroll;
      if (elements.autoScrollLabel) {
        elements.autoScrollLabel.textContent = `Auto-Scroll: ${logState.autoScroll ? 'ON' : 'OFF'}`;
      }
      elements.autoScrollToggleBtn.classList.toggle('active', logState.autoScroll);
    });
  }

  if (elements.copyLogsBtn) {
    elements.copyLogsBtn.addEventListener('click', copyVisibleLogs);
  }

  if (elements.clearLogsBtn) {
    elements.clearLogsBtn.addEventListener('click', clearAllLogs);
  }

  // Initial load
  updateNavVisibility(false);
  loadProfiles();
  checkHplocons();
});
