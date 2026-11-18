// Sound Effects for UNO Show 'Em No Mercy
// Loads authentic sounds with automatic Web Audio synthesizer fallback

class SoundEffects {
    constructor() {
        this.enabled = true;
        this.audioCache = {};
        this._loadAudioFiles();
    }

    _loadAudioFiles() {
        const soundNames = ["play", "draw", "eliminated", "reverse", "skip", "hover"];
        soundNames.forEach(name => {
            const audio = new Audio(`/static/sounds/${name}.mp3`);
            audio.preload = "auto";
            this.audioCache[name] = audio;
        });
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }

    _playFileOrSynth(name, synthFallback) {
        if (!this.enabled) return;
        const audio = this.audioCache[name];
        if (audio) {
            try {
                audio.currentTime = 0;
                audio.play().catch(() => {
                    if (synthFallback) synthFallback();
                });
                return;
            } catch (e) {
                // fall through to synth
            }
        }
        if (synthFallback) synthFallback();
    }

    playCard() {
        this._playFileOrSynth("play");
    }

    drawCard() {
        this._playFileOrSynth("draw");
    }

    penaltyStack() {
        this._playFileOrSynth("reverse");
    }

    mercyKnockout() {
        this._playFileOrSynth("eliminated");
    }

    skipTurn() {
        this._playFileOrSynth("skip");
    }

    reverseTurn() {
        this._playFileOrSynth("reverse");
    }

    cardHover() {
        this._playFileOrSynth("hover");
    }

    unoShout() {
        this.playCard();
    }

    victory() {
        this.playCard();
    }
}

window.sounds = new SoundEffects();
