/* Independent operator codes pair this HA connection; no microphone opens here. */
class JarvisSpeakerPairCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
    if (!this.shadowRoot) this.attachShadow({mode: 'open'});
    this.render();
  }
  set hass(value) { this._hass = value; }
  connectedCallback() {
    clearInterval(this._statusTimer);
    this._statusTimer = setInterval(() => this.refreshStatus(), 2000);
    this.refreshStatus();
  }
  disconnectedCallback() { clearInterval(this._statusTimer); }
  getCardSize() { return 3; }
  render() {
    this.shadowRoot.innerHTML = '<style>:host{display:block}ha-card{padding:22px;border:1px solid #315b70;background:#0a2030;color:#e7f6fc;border-radius:14px}h2{margin:0 0 12px;font-size:21px}p{line-height:1.55;color:#b7ceda;font-size:14px}.row{display:flex;gap:9px;flex-wrap:wrap}input{flex:1;min-width:170px;min-height:42px;background:#071724;border:1px solid #426d7f;border-radius:7px;padding:0 11px;color:#e7f6fc}button{padding:10px 16px;min-height:42px;border:1px solid #70dfed;border-radius:7px;color:#082533;background:#70dfed;cursor:pointer}.off{background:transparent;color:#d4e9f3}button:disabled{opacity:.4}.status{min-height:22px;color:#70dfed}small{color:#a6bfcc}</style><ha-card><h2>Speaker pilot · Development computer</h2><p>After enrolling through the private Voice setup page, enter its one-use microphone code here. Pairing lasts up to 30 minutes and ends if this HA connection closes.</p><div class="row"><input type="password" autocomplete="off" aria-label="Private microphone pairing code" placeholder="Private pairing code"><button class="pair">Pair microphone</button><button class="off">Unpair</button></div><p class="status" role="status">Not paired</p><small>Matched speech can select your already-shared profile for routine questions. Voice matching grants no private access or action approval.</small></ha-card>';
    this.shadowRoot.querySelector('.pair').addEventListener('click', () => this.pair());
    this.shadowRoot.querySelector('.off').addEventListener('click', () => this.unpair());
  }
  status(text) { this.shadowRoot.querySelector('.status').textContent = text; }
  async refreshStatus() {
    if (!this._hass || !this.isConnected || !this.shadowRoot || this._statusPending) return;
    this._statusPending = true;
    try {
      const result = await this._hass.callWS({type: 'jarvis_conversation/speaker_status'});
      const labels = {
        not_configured: 'Pilot adapter unavailable', not_paired: 'Not paired · normal shared answers',
        pairing_expired: 'Pairing expired · create a fresh code; your saved voice is unchanged',
        paired: 'Paired · ready for the existing development microphone', listening: 'Listening for this request',
        collecting: 'Collecting activated speech', analysing: 'Checking the optional voice match',
        matched: 'Benny voice match · shared-profile personalisation only',
        voice_uncertain: 'Anonymous · voice not confidently matched',
        speech_quality_rejected: 'Anonymous · speech quality/overlap check did not pass',
        recognizer_unavailable: 'Anonymous · recogniser unavailable; warm it in private Voice setup',
        calibration_unavailable: 'Anonymous · calibration/consent unavailable',
        recognition_timeout: 'Anonymous · optional recognition deadline reached',
        gateway_unavailable: 'Anonymous · recognition connection unavailable',
        audio_too_short: 'Anonymous · recording too short for recognition',
        speech_not_confirmed: 'Anonymous · no confirmed speech start',
        invalid_audio: 'Anonymous · audio format or capture limit failed',
        sender_unavailable: 'Anonymous · audio sender unavailable/busy',
        cancelled: 'Anonymous · listening was cancelled', expired: 'Anonymous · capture expired',
        already_consumed: 'Anonymous · result was already used', capacity_reached: 'Anonymous · recogniser busy'
      };
      const label = labels[result.last_result] || 'Anonymous · no usable recognition result';
      this.status(label + (result.paired ? ' · pairing '+Math.ceil(result.expires_in/60)+' min remaining' : ''));
    } catch { this.status('Pilot status unavailable · no voice match can be confirmed'); }
    finally { this._statusPending = false; }
  }
  async pair() {
    const field = this.shadowRoot.querySelector('input');
    const code = field.value.trim(); field.value = '';
    if (!code || !this._hass) return;
    const button = this.shadowRoot.querySelector('.pair'); button.disabled = true;
    try {
      await this._hass.callWS({type: 'jarvis_conversation/pair_speaker', code});
      this.status('Paired · use the existing development microphone card');
      await this.refreshStatus();
    } catch {
      this.status('Pairing failed. Create a fresh code in private Voice setup.');
    } finally { button.disabled = false; }
  }
  async unpair() {
    try {
      await this._hass.callWS({type: 'jarvis_conversation/unpair_speaker'});
      this.status('Unpaired · normal shared answers');
      await this.refreshStatus();
    } catch { this.status('Could not confirm unpairing. Close this HA connection to end its pairing.'); }
  }
}
if (!customElements.get('jarvis-speaker-pair-card')) customElements.define('jarvis-speaker-pair-card', JarvisSpeakerPairCard);
window.customCards = window.customCards || [];
window.customCards.push({type: 'jarvis-speaker-pair-card', name: 'Jarvis Speaker Pilot', description: 'Private operator pairing for the existing development microphone'});
