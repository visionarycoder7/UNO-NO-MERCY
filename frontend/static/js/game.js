// Game UI & Interaction Manager for UNO Show 'Em No Mercy

class UnoGameRenderer {
    constructor() {
        this.gameState = null;
        this.myPlayerId = null;
        this.ws = null;

        this.tableEl = document.getElementById('tableArena');
        this.opponentsContainer = document.getElementById('opponentsContainer');
        this.cardsFanEl = document.getElementById('cardsFan');
        this.discardCardEl = document.getElementById('topDiscardCard');
        this.drawPileCountEl = document.getElementById('drawPileCount');
        this.directionIndicator = document.getElementById('directionIndicator');
        this.activeColorBadge = document.getElementById('activeColorBadge');
        this.penaltyBanner = document.getElementById('penaltyStackBanner');
        this.penaltyValueEl = document.getElementById('penaltyValueText');
        this.turnPill = document.getElementById('turnStatusPill');
        this.unoBtn = document.getElementById('unoCallBtn');
        this.eventFeed = document.getElementById('eventFeedBox');

        this._setupListeners();
    }

    setWebSocket(ws, myPlayerId) {
        this.ws = ws;
        this.myPlayerId = myPlayerId;
    }

    _setupListeners() {
        // Draw deck click
        const deckCard = document.getElementById('deckCardElement');
        if (deckCard) {
            deckCard.addEventListener('click', () => {
                if (this.gameState && this.gameState.can_draw) {
                    this.sendAction({ type: 'draw' });
                    window.sounds.drawCard();
                }
            });
        }

        // UNO Button click
        if (this.unoBtn) {
            this.unoBtn.addEventListener('click', () => {
                if (this.gameState && this.gameState.can_call_uno) {
                    this.sendAction({ type: 'call_uno' });
                    window.sounds.unoShout();
                }
            });
        }

        // Color selection buttons
        document.querySelectorAll('.color-opt-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const color = e.currentTarget.getAttribute('data-color');
                const modal = document.getElementById('colorPickerModal');
                const actionType = modal.getAttribute('data-action') || 'choose_color';
                modal.classList.remove('active');

                this.sendAction({
                    type: 'resolve_action',
                    action: actionType,
                    color: color
                });
                window.sounds.playCard();
            });
        });
    }

    sendAction(payload) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload));
        }
    }

    updateState(state) {
        const prevState = this.gameState;
        this.gameState = state;

        // Sound triggers
        if (prevState) {
            if (state.pending_penalty > prevState.pending_penalty) {
                window.sounds.penaltyStack();
            } else if (state.draw_pile_count < prevState.draw_pile_count) {
                window.sounds.drawCard();
            }
        }

        this.renderTurnIndicator();
        this.renderPenaltyBanner();
        this.renderDirection();
        this.renderCenterPiles();
        this.renderOpponents();
        this.renderMyHand();
        this.renderEventFeed();
        this.checkPendingActions();
    }

    renderTurnIndicator() {
        const isMyTurn = (this.gameState.current_player_id === this.myPlayerId);
        if (isMyTurn) {
            this.turnPill.textContent = "🔥 YOUR TURN!";
            this.turnPill.className = "turn-pill my-turn";
        } else {
            this.turnPill.textContent = `${this.gameState.current_player_name}'s Turn`;
            this.turnPill.className = "turn-pill";
        }
    }

    renderPenaltyBanner() {
        if (this.gameState.pending_penalty > 0) {
            this.penaltyBanner.classList.add('active');
            this.penaltyValueEl.textContent = `+${this.gameState.pending_penalty}`;
        } else {
            this.penaltyBanner.classList.remove('active');
        }
    }

    renderDirection() {
        if (this.gameState.direction === 1) {
            this.directionIndicator.className = "direction-indicator";
        } else {
            this.directionIndicator.className = "direction-indicator ccw";
        }
    }

    renderCenterPiles() {
        // Draw pile count
        this.drawPileCountEl.textContent = `${this.gameState.draw_pile_count} Cards`;

        const deckCard = document.getElementById('deckCardElement');
        if (this.gameState.can_draw) {
            deckCard.classList.add('highlight-draw');
        } else {
            deckCard.classList.remove('highlight-draw');
        }

        // Discard top card
        const top = this.gameState.top_card;
        if (top) {
            this.renderCardElement(this.discardCardEl, top, false);
        }

        // Active color badge
        const color = this.gameState.current_color || 'wild';
        this.activeColorBadge.textContent = color.toUpperCase();
        this.activeColorBadge.style.background = this.getColorHex(color);
        this.activeColorBadge.style.color = (color === 'yellow') ? '#000' : '#fff';
    }

    getColorHex(color) {
        switch (color) {
            case 'red': return '#ff2a5f';
            case 'yellow': return '#ffd000';
            case 'green': return '#00e676';
            case 'blue': return '#00b0ff';
            default: return '#7b2cbf';
        }
    }

    renderOpponents() {
        this.opponentsContainer.innerHTML = '';
        const allPlayers = this.gameState.players;
        const otherPlayers = allPlayers.filter(p => p.id !== this.myPlayerId);

        // Position mapping based on player count
        const count = otherPlayers.length;
        const positions = this.getSeatPositions(count);

        otherPlayers.forEach((p, idx) => {
            const pod = document.createElement('div');
            const posClass = positions[idx] || 'pos-top';
            pod.className = `opponent-pod ${posClass}`;

            if (p.is_current) pod.classList.add('active-turn');
            if (p.is_eliminated) pod.classList.add('eliminated');

            // Gauge status
            let gaugeClass = "safe";
            let gaugeText = `${p.card_count} Cards`;
            if (p.is_eliminated) {
                gaugeClass = "dead";
                gaugeText = "💀 KNOCKED OUT";
            } else if (p.card_count >= 20) {
                gaugeClass = "critical";
                gaugeText = `⚠️ CRITICAL: ${p.card_count}/25`;
            } else if (p.card_count >= 15) {
                gaugeClass = "warning";
                gaugeText = `⚠️ ${p.card_count}/25`;
            }

            pod.innerHTML = `
                <div class="opponent-avatar-box">
                    <span>${this.getAvatarEmoji(p.avatar)}</span>
                </div>
                <div class="opponent-info-box">
                    <span class="opponent-name">${this.escapeHtml(p.name)}</span>
                    <span class="mercy-gauge ${gaugeClass}">${gaugeText}</span>
                </div>
            `;

            // UNO callout catch listener
            if (p.card_count === 1 && !p.called_uno && !p.is_eliminated) {
                const catchBtn = document.createElement('button');
                catchBtn.className = "btn-primary";
                catchBtn.style.padding = "4px 8px";
                catchBtn.style.fontSize = "0.75rem";
                catchBtn.textContent = "🚨 Catch UNO!";
                catchBtn.onclick = () => {
                    this.sendAction({ type: 'catch_uno', target_id: p.id });
                };
                pod.querySelector('.opponent-info-box').appendChild(catchBtn);
            }

            this.opponentsContainer.appendChild(pod);
        });
    }

    getSeatPositions(count) {
        if (count === 1) return ['pos-top'];
        if (count === 2) return ['pos-top-left', 'pos-top-right'];
        if (count === 3) return ['pos-left', 'pos-top', 'pos-right'];
        if (count === 4) return ['pos-left', 'pos-top-left', 'pos-top-right', 'pos-right'];
        return ['pos-left', 'pos-top-left', 'pos-top', 'pos-top-right', 'pos-right'];
    }

    renderMyHand() {
        this.cardsFanEl.innerHTML = '';
        const validIds = new Set(this.gameState.my_valid_cards || []);
        const myHand = this.gameState.my_hand || [];

        // Check UNO button pulse
        if (this.gameState.can_call_uno) {
            this.unoBtn.classList.add('pulse');
            this.unoBtn.disabled = false;
        } else {
            this.unoBtn.classList.remove('pulse');
            this.unoBtn.disabled = true;
        }

        myHand.forEach(card => {
            const cardEl = document.createElement('div');
            const isPlayable = validIds.has(card.id);
            this.renderCardElement(cardEl, card, isPlayable);

            if (isPlayable) {
                cardEl.addEventListener('click', () => {
                    this.onPlayCardClicked(card);
                });
            }

            this.cardsFanEl.appendChild(cardEl);
        });
    }

    onPlayCardClicked(card) {
        // If Wild card, show color picker modal immediately
        if (card.is_wild && card.card_type !== 'wild_roulette') {
            this.showColorPickerModal(card.id, 'choose_color');
            return;
        }

        // If Roulette, show color picker modal
        if (card.card_type === 'wild_roulette') {
            this.showColorPickerModal(card.id, 'choose_roulette_color');
            return;
        }

        // If 7 card, check if multiple opponents exist
        if (card.card_type === 'number' && card.value === 7) {
            const activeOpponents = this.gameState.players.filter(p => p.id !== this.myPlayerId && !p.is_eliminated);
            if (activeOpponents.length > 1) {
                this.showSwapHandsModal(card.id, activeOpponents);
                return;
            }
        }

        // Normal play
        this.sendAction({
            type: 'play_card',
            card_id: card.id
        });
        window.sounds.playCard();
    }

    showColorPickerModal(cardId, actionType) {
        const modal = document.getElementById('colorPickerModal');
        modal.setAttribute('data-card-id', cardId);
        modal.setAttribute('data-action', actionType);
        modal.classList.add('active');
    }

    showSwapHandsModal(cardId, opponents) {
        const modal = document.getElementById('swapHandModal');
        const list = document.getElementById('swapTargetsList');
        list.innerHTML = '';

        opponents.forEach(p => {
            const btn = document.createElement('button');
            btn.className = "target-player-btn";
            btn.innerHTML = `
                <span>${this.getAvatarEmoji(p.avatar)} ${this.escapeHtml(p.name)}</span>
                <span class="mercy-gauge safe">${p.card_count} Cards</span>
            `;
            btn.onclick = () => {
                modal.classList.remove('active');
                this.sendAction({
                    type: 'play_card',
                    card_id: cardId,
                    target_player_id: p.id
                });
                window.sounds.playCard();
            };
            list.appendChild(btn);
        });

        modal.classList.add('active');
    }

    checkPendingActions() {
        if (this.gameState.pending_action) {
            if (this.gameState.pending_action === 'choose_color') {
                this.showColorPickerModal(this.gameState.action_context.card_id, 'choose_color');
            } else if (this.gameState.pending_action === 'choose_roulette_color') {
                this.showColorPickerModal(this.gameState.action_context.card_id, 'choose_roulette_color');
            } else if (this.gameState.pending_action === 'swap_hand') {
                const opponents = this.gameState.players.filter(p => p.id !== this.myPlayerId && !p.is_eliminated);
                this.showSwapHandsModal(this.gameState.action_context.card_id, opponents);
            }
        }
    }

    renderCardElement(cardEl, card, isPlayable = false) {
        cardEl.className = `uno-card color-${card.color} ${isPlayable ? 'playable' : 'unplayable'}`;

        let symbol = "";
        let corner = "";
        let badge = "";

        switch (card.card_type) {
            case 'number':
                symbol = card.value.toString();
                corner = card.value.toString();
                if (card.value === 0) badge = "PASS HAND";
                if (card.value === 7) badge = "SWAP HAND";
                break;
            case 'skip':
                symbol = "🚫";
                corner = "🚫";
                break;
            case 'skip_everyone':
                symbol = "⚡🚫";
                corner = "⚡";
                badge = "SKIP ALL";
                break;
            case 'reverse':
                symbol = "🔁";
                corner = "🔁";
                break;
            case 'draw_2':
                symbol = "+2";
                corner = "+2";
                break;
            case 'draw_4':
                symbol = "+4";
                corner = "+4";
                break;
            case 'discard_all':
                symbol = "🗑️";
                corner = "ALL";
                badge = "DISCARD ALL";
                break;
            case 'wild_roulette':
                symbol = "🎰";
                corner = "🎰";
                badge = "ROULETTE";
                break;
            case 'wild_reverse_draw_4':
                symbol = "🔁+4";
                corner = "+4";
                badge = "REV +4";
                break;
            case 'wild_draw_6':
                symbol = "+6";
                corner = "+6";
                badge = "WILD +6";
                break;
            case 'wild_draw_10':
                symbol = "+10";
                corner = "+10";
                badge = "WILD +10";
                break;
            default:
                symbol = "?";
                corner = "?";
        }

        cardEl.innerHTML = `
            <span class="card-corner-symbol top-left">${corner}</span>
            <div class="card-oval">
                <span class="card-main-symbol">${symbol}</span>
            </div>
            <span class="card-corner-symbol bottom-right">${corner}</span>
            ${badge ? `<span class="card-wild-badge">${badge}</span>` : ''}
        `;
    }

    renderEventFeed() {
        if (!this.eventFeed) return;
        this.eventFeed.innerHTML = '';
        const events = this.gameState.recent_events || [];
        events.slice(-5).forEach(e => {
            const item = document.createElement('div');
            item.className = 'event-feed-item';
            item.textContent = e.message;
            this.eventFeed.appendChild(item);
        });
    }

    getAvatarEmoji(avatarId) {
        const avatars = {
            'avatar1': '🦊',
            'avatar2': '🐺',
            'avatar3': '🦁',
            'avatar4': '🐯',
            'avatar5': '🐉',
            'avatar6': '🤖'
        };
        return avatars[avatarId] || '👤';
    }

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
}

window.UnoGameRenderer = UnoGameRenderer;

