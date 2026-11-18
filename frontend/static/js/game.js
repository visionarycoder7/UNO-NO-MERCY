// Game UI & Interaction Renderer matching unonomercy.in logic

class UnoGameRenderer {
    constructor() {
        this.gameState = null;
        this.myPlayerId = null;
        this.ws = null;

        this.opponentsContainer = document.getElementById('opponentsContainer');
        this.cardsFanEl = document.getElementById('cardsFan');
        this.topCardImg = document.getElementById('topCardImg');
        this.drawPileCountEl = document.getElementById('drawPileCount');
        this.directionArrowImg = document.getElementById('directionArrowImg');
        this.activeColorBadge = document.getElementById('activeColorBadge');
        this.penaltyBanner = document.getElementById('penaltyStackBanner');
        this.penaltyValueEl = document.getElementById('penaltyValueText');
        this.turnPill = document.getElementById('turnStatusPill');
        this.unoBtn = document.getElementById('unoCallBtn');
        this.floatingEmojiLayer = document.getElementById('floatingEmojiLayer');

        this._setupListeners();
    }

    setWebSocket(ws, myPlayerId) {
        this.ws = ws;
        this.myPlayerId = myPlayerId;
    }

    _setupListeners() {
        // Draw pile click
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
        document.querySelectorAll('.color-btn').forEach(btn => {
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

        if (prevState) {
            if (state.pending_penalty > prevState.pending_penalty) {
                window.sounds.penaltyStack();
            } else if (state.draw_pile_count < prevState.draw_pile_count) {
                window.sounds.drawCard();
            } else if (state.direction !== prevState.direction) {
                window.sounds.reverseTurn();
            }
        }

        this.renderTurnIndicator();
        this.renderPenaltyBanner();
        this.renderDirection();
        this.renderCenterPiles();
        this.renderOpponents();
        this.renderMyHand();
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
        if (this.directionArrowImg) {
            if (this.gameState.direction === 1) {
                this.directionArrowImg.src = "/static/images/arrow.webp";
                this.directionArrowImg.className = "direction-arrow-img";
            } else {
                this.directionArrowImg.src = "/static/images/arrowreverse.webp";
                this.directionArrowImg.className = "direction-arrow-img reverse";
            }
        }
    }

    renderCenterPiles() {
        this.drawPileCountEl.textContent = `${this.gameState.draw_pile_count} Cards`;

        const deckCard = document.getElementById('deckCardElement');
        if (this.gameState.can_draw) {
            deckCard.classList.add('highlight-draw');
        } else {
            deckCard.classList.remove('highlight-draw');
        }

        // Top discard card
        const top = this.gameState.top_card;
        if (top && this.topCardImg) {
            this.topCardImg.src = top.image_url;
            this.topCardImg.alt = top.display_name;
        }

        // Active color
        const color = this.gameState.current_color || 'wild';
        this.activeColorBadge.textContent = color.toUpperCase();
        this.activeColorBadge.style.background = this.getColorHex(color);
        this.activeColorBadge.style.color = (color === 'yellow') ? '#000' : '#fff';
    }

    getColorHex(color) {
        switch (color) {
            case 'red': return '#ff1a4b';
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

        const positions = this.getSeatPositions(otherPlayers.length);

        otherPlayers.forEach((p, idx) => {
            const pod = document.createElement('div');
            const posClass = positions[idx] || 'pos-top';
            pod.className = `opponent-pod ${posClass}`;
            pod.id = `pod_${p.id}`;

            if (p.is_current) pod.classList.add('active-turn');
            if (p.is_eliminated) pod.classList.add('eliminated');

            let meterClass = "safe";
            let meterText = `${p.card_count} Cards`;
            if (p.is_eliminated) {
                meterClass = "dead";
                meterText = "💀 ELIMINATED";
            } else if (p.card_count >= 20) {
                meterClass = "critical";
                meterText = `⚠️ CRITICAL: ${p.card_count}/25`;
            } else if (p.card_count >= 15) {
                meterClass = "warning";
                meterText = `⚠️ ${p.card_count}/25`;
            }

            pod.innerHTML = `
                <div class="opponent-avatar-box">
                    <span>${this.getAvatarEmoji(p.avatar, p.is_ai)}</span>
                </div>
                <div class="opponent-info-box">
                    <span class="opponent-name">${p.is_ai ? '🤖 ' : ''}${this.escapeHtml(p.name)}</span>
                    <span class="mercy-meter ${meterClass}">${meterText}</span>
                </div>
            `;

            // UNO Catch button
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

        if (this.gameState.can_call_uno) {
            this.unoBtn.classList.add('pulse');
            this.unoBtn.disabled = false;
        } else {
            this.unoBtn.classList.remove('pulse');
            this.unoBtn.disabled = true;
        }

        myHand.forEach(card => {
            const wrapper = document.createElement('div');
            const isPlayable = validIds.has(card.id);
            wrapper.className = `hand-card-wrapper ${isPlayable ? 'playable' : 'unplayable'}`;

            wrapper.innerHTML = `<img src="${card.image_url}" alt="${card.display_name}" class="hand-card-img" />`;

            if (isPlayable) {
                wrapper.addEventListener('mouseenter', () => window.sounds.cardHover());
                wrapper.addEventListener('click', () => this.onPlayCardClicked(card));
            }

            this.cardsFanEl.appendChild(wrapper);
        });
    }

    onPlayCardClicked(card) {
        if (card.is_wild && card.card_type !== 'roulette') {
            this.showColorPickerModal(card.id, 'choose_color');
            return;
        }

        if (card.card_type === 'roulette') {
            this.showColorPickerModal(card.id, 'choose_roulette_color');
            return;
        }

        if (card.card_type === 'number' && card.value === '7') {
            const activeOpponents = this.gameState.players.filter(p => p.id !== this.myPlayerId && !p.is_eliminated);
            if (activeOpponents.length > 1) {
                this.showSwapHandsModal(card.id, activeOpponents);
                return;
            }
        }

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
            btn.className = "btn-secondary";
            btn.style.display = "flex";
            btn.style.justifyContent = "space-between";
            btn.style.alignItems = "center";
            btn.innerHTML = `
                <span>${this.getAvatarEmoji(p.avatar, p.is_ai)} ${this.escapeHtml(p.name)}</span>
                <span class="mercy-meter safe">${p.card_count} Cards</span>
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

    spawnFloatingEmoji(emoji, senderId) {
        if (!this.floatingEmojiLayer) return;

        const el = document.createElement('div');
        el.className = 'floating-emoji';
        el.textContent = emoji;

        let leftPos = window.innerWidth / 2;
        let topPos = window.innerHeight * 0.7;

        if (senderId && senderId !== this.myPlayerId) {
            const pod = document.getElementById(`pod_${senderId}`);
            if (pod) {
                const rect = pod.getBoundingClientRect();
                leftPos = rect.left + rect.width / 2;
                topPos = rect.top + rect.height / 2;
            }
        }

        el.style.left = `${leftPos}px`;
        el.style.top = `${topPos}px`;

        this.floatingEmojiLayer.appendChild(el);
        setTimeout(() => el.remove(), 2500);
    }

    getAvatarEmoji(avatarId, isAi = false) {
        if (isAi) return '🤖';
        const avatars = {
            'avatar1': '🦊', 'avatar2': '🐺', 'avatar3': '🦁',
            'avatar4': '🐯', 'avatar5': '🐉', 'avatar6': '🤖'
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
