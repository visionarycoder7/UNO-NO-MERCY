// Game UI & Interaction Renderer matching UNO No Mercy.html gameplay logic

const COLOR_MAP = {
    'R': { name: 'Red', hex: '#d72600' },
    'Y': { name: 'Yellow', hex: '#d99a00' },
    'G': { name: 'Green', hex: '#2a9d48' },
    'B': { name: 'Blue', hex: '#0b6fd1' },
    'W': { name: 'Wild', hex: '#222222' }
};

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

        // Draw Action Button in Hand Bar
        const drawBtn = document.getElementById('drawCardActionBtn');
        if (drawBtn) {
            drawBtn.addEventListener('click', () => {
                if (this.gameState && this.gameState.can_draw) {
                    this.sendAction({ type: 'draw' });
                    window.sounds.drawCard();
                }
            });
        }

        // UNO Call Button
        const unoBtn = document.getElementById('unoCallBtn');
        if (unoBtn) {
            unoBtn.addEventListener('click', () => {
                this.sendAction({ type: 'call_uno' });
                window.sounds.unoShout();
                unoBtn.classList.add('pulse');
                setTimeout(() => unoBtn.classList.remove('pulse'), 1000);
            });
        }

        // Color selection buttons
        document.querySelectorAll('.color-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const colorCode = e.currentTarget.getAttribute('data-color');
                const modal = document.getElementById('colorPickerModal');
                const actionType = modal.getAttribute('data-action') || 'color';
                const cardId = modal.getAttribute('data-card-id');
                modal.classList.remove('active');

                if (cardId && cardId !== 'null' && cardId !== 'undefined' && actionType === 'color') {
                    this.sendAction({
                        type: 'play_card',
                        card_id: cardId,
                        color: colorCode
                    });
                } else {
                    this.sendAction({
                        type: 'resolve_action',
                        action: actionType,
                        color: colorCode
                    });
                }
                modal.removeAttribute('data-card-id');
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

        // Active color badge
        const color = this.gameState.current_color || 'R';
        const colorInfo = COLOR_MAP[color] || { name: 'Red', hex: '#d72600' };
        this.activeColorBadge.textContent = colorInfo.name.toUpperCase();
        this.activeColorBadge.style.background = colorInfo.hex;
        this.activeColorBadge.style.color = (color === 'Y') ? '#000' : '#fff';
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
            let meterText = `${p.card_count} / 25 cards`;
            if (p.is_eliminated) {
                meterClass = "dead";
                meterText = "💀 OUT (Mercy)";
            } else if (p.card_count >= 20) {
                meterClass = "critical";
                meterText = `⚠️ WARN: ${p.card_count} / 25`;
            } else if (p.card_count >= 15) {
                meterClass = "warning";
                meterText = `⚠️ ${p.card_count} / 25`;
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
        let myHand = this.gameState.my_hand || [];

        // Sort hand matching UNO No Mercy.html:
        // 'RYGBW'.indexOf(x.color) - 'RYGBW'.indexOf(y.color) || (x.type > y.type ? 1 : -1)
        myHand = [...myHand].sort((x, y) => {
            const order = 'RYGBW';
            const cDiff = order.indexOf(x.color) - order.indexOf(y.color);
            if (cDiff !== 0) return cDiff;
            return (x.type > y.type ? 1 : -1);
        });

        const unoBtn = document.getElementById('unoCallBtn');
        if (unoBtn) {
            unoBtn.disabled = myHand.length > 2;
        }

        const drawBtn = document.getElementById('drawCardActionBtn');
        if (drawBtn) {
            if (this.gameState && this.gameState.can_draw) {
                drawBtn.disabled = false;
                drawBtn.classList.add('can-draw');
                if (this.gameState.pending_penalty > 0) {
                    drawBtn.innerHTML = `⚠️ DRAW +${this.gameState.pending_penalty} (PENALTY)`;
                    drawBtn.classList.add('penalty');
                } else {
                    drawBtn.innerHTML = `📥 DRAW CARD`;
                    drawBtn.classList.remove('penalty');
                }
            } else {
                drawBtn.disabled = true;
                drawBtn.classList.remove('can-draw', 'penalty');
                drawBtn.innerHTML = `📥 DRAW CARD`;
            }
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
        // 7 Hand Swap modal
        if (card.type === '7') {
            const activeOpponents = this.gameState.players.filter(p => p.id !== this.myPlayerId && !p.is_eliminated);
            if (activeOpponents.length > 1) {
                this.showSwapHandsModal(card.id, activeOpponents);
                return;
            }
        }

        // Wild color picker
        if (card.color === 'W' && card.type !== 'roul') {
            this.showColorPickerModal(card.id, 'color', 'Choose a color');
            return;
        }

        // Normal play
        this.sendAction({
            type: 'play_card',
            card_id: card.id
        });
        window.sounds.playCard();
    }

    showColorPickerModal(cardId, actionType, title = 'Choose a color') {
        const modal = document.getElementById('colorPickerModal');
        modal.querySelector('h2').textContent = title;
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
                <span class="mercy-meter safe">${p.card_count} cards</span>
            `;
            btn.onclick = () => {
                modal.classList.remove('active');
                if (this.gameState && this.gameState.pending_action === 'target') {
                    this.sendAction({
                        type: 'resolve_action',
                        action: 'target',
                        target_player_id: p.id
                    });
                } else {
                    this.sendAction({
                        type: 'play_card',
                        card_id: cardId,
                        target_player_id: p.id
                    });
                }
                window.sounds.playCard();
            };
            list.appendChild(btn);
        });

        modal.classList.add('active');
    }

    checkPendingActions() {
        if (this.gameState.pending_action) {
            if (this.gameState.pending_action === 'color') {
                this.showColorPickerModal(this.gameState.action_context.card_id, 'color', 'Choose a color');
            } else if (this.gameState.pending_action === 'roul') {
                this.showColorPickerModal(null, 'roul', 'Pick a color to draw until!');
            } else if (this.gameState.pending_action === 'target') {
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
