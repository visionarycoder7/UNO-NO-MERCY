// Application Coordinator for UNO Show 'Em No Mercy

document.addEventListener('DOMContentLoaded', () => {
    // Current user & room state
    let currentUser = null;
    let currentRoom = null;
    let myPlayerId = null;
    let ws = null;
    let gameRenderer = null;

    // View Elements
    const authView = document.getElementById('authView');
    const lobbyView = document.getElementById('lobbyView');
    const waitingView = document.getElementById('waitingView');
    const gameView = document.getElementById('gameView');

    // Header Elements
    const userBadge = document.getElementById('userBadge');
    const userNameDisplay = document.getElementById('userNameDisplay');
    const userAvatarDisplay = document.getElementById('userAvatarDisplay');
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    const chatToggleBtn = document.getElementById('chatToggleBtn');
    const chatDrawer = document.getElementById('chatDrawer');

    // Lobby Elements
    const hostNameInput = document.getElementById('hostNameInput');
    const joinCodeInput = document.getElementById('joinCodeInput');
    const joinNameInput = document.getElementById('joinNameInput');
    const createRoomBtn = document.getElementById('createRoomBtn');
    const joinRoomBtn = document.getElementById('joinRoomBtn');
    const activeRoomsList = document.getElementById('activeRoomsList');

    // Waiting Room Elements
    const waitingRoomCode = document.getElementById('waitingRoomCode');
    const waitingSeatsGrid = document.getElementById('waitingSeatsGrid');
    const toggleReadyBtn = document.getElementById('toggleReadyBtn');
    const startGameBtn = document.getElementById('startGameBtn');
    const copyRoomCodeBtn = document.getElementById('copyRoomCodeBtn');

    // Chat Elements
    const chatMessagesEl = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendChatBtn = document.getElementById('sendChatBtn');
    const closeChatBtn = document.getElementById('closeChatBtn');

    // Victory Modal Elements
    const victoryModal = document.getElementById('victoryModal');
    const winnerNameEl = document.getElementById('winnerNameText');
    const winReasonEl = document.getElementById('winReasonText');
    const returnLobbyBtn = document.getElementById('returnLobbyBtn');

    let selectedMaxPlayers = 6;
    let selectedAvatar = 'avatar1';

    // ---------------- Switch View Helper ---------------- //
    function switchView(viewName) {
        document.querySelectorAll('.view-section').forEach(sec => sec.classList.remove('active'));
        if (viewName === 'lobby') lobbyView.classList.add('active');
        if (viewName === 'waiting') waitingView.classList.add('active');
        if (viewName === 'game') gameView.classList.add('active');
    }

    // ---------------- Avatar & Player Limits ---------------- //
    document.querySelectorAll('.avatar-opt').forEach(opt => {
        opt.addEventListener('click', (e) => {
            document.querySelectorAll('.avatar-opt').forEach(o => o.classList.remove('selected'));
            e.currentTarget.classList.add('selected');
            selectedAvatar = e.currentTarget.getAttribute('data-avatar');
        });
    });

    document.querySelectorAll('.limit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.limit-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            selectedMaxPlayers = parseInt(e.currentTarget.getAttribute('data-limit'), 10);
        });
    });

    // Sound toggle
    soundToggleBtn.addEventListener('click', () => {
        const enabled = window.sounds.toggle();
        soundToggleBtn.textContent = enabled ? '🔊' : '🔇';
    });

    // Chat drawer toggle
    chatToggleBtn.addEventListener('click', () => {
        chatDrawer.classList.toggle('active');
    });
    if (closeChatBtn) {
        closeChatBtn.addEventListener('click', () => {
            chatDrawer.classList.remove('active');
        });
    }

    // Quick emotes
    document.querySelectorAll('.emote-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const emote = e.currentTarget.textContent;
            sendChatMessage(emote);
        });
    });

    // Send Chat
    function sendChatMessage(text) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        const msg = text || chatInput.value.trim();
        if (!msg) return;
        ws.send(JSON.stringify({ type: 'chat', message: msg }));
        chatInput.value = '';
    }

    sendChatBtn.addEventListener('click', () => sendChatMessage());
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    // ---------------- Create Room ---------------- //
    createRoomBtn.addEventListener('click', async () => {
        const hostName = hostNameInput.value.trim();
        if (!hostName) {
            alert('Please enter your name.');
            return;
        }

        try {
            createRoomBtn.disabled = true;
            createRoomBtn.textContent = 'Creating...';

            const res = await window.API.createRoom(hostName, selectedAvatar, selectedMaxPlayers);
            myPlayerId = res.host_id;
            currentRoom = res.room;
            currentUser = { name: hostName, avatar: selectedAvatar };

            updateHeaderUser(hostName, selectedAvatar);
            connectWebSocket(res.room_code, myPlayerId);
            showWaitingRoom(res.room);
        } catch (err) {
            alert('Failed to create room: ' + err.message);
        } finally {
            createRoomBtn.disabled = false;
            createRoomBtn.textContent = '🔥 Create Room';
        }
    });

    // ---------------- Join Room ---------------- //
    joinRoomBtn.addEventListener('click', async () => {
        const code = joinCodeInput.value.trim().toUpperCase();
        const playerName = joinNameInput.value.trim();

        if (!code || code.length < 4) {
            alert('Please enter a valid 6-character room code.');
            return;
        }
        if (!playerName) {
            alert('Please enter your player name.');
            return;
        }

        try {
            joinRoomBtn.disabled = true;
            joinRoomBtn.textContent = 'Joining...';

            const res = await window.API.joinRoom(code, playerName, selectedAvatar);
            myPlayerId = res.player_id;
            currentRoom = res.room;
            currentUser = { name: playerName, avatar: selectedAvatar };

            updateHeaderUser(playerName, selectedAvatar);
            connectWebSocket(code, myPlayerId);
            showWaitingRoom(res.room);
        } catch (err) {
            alert('Failed to join room: ' + err.message);
        } finally {
            joinRoomBtn.disabled = false;
            joinRoomBtn.textContent = 'Join Room';
        }
    });

    // Copy room code button
    copyRoomCodeBtn.addEventListener('click', () => {
        if (currentRoom) {
            navigator.clipboard.writeText(currentRoom.code);
            copyRoomCodeBtn.textContent = '✅ Copied!';
            setTimeout(() => { copyRoomCodeBtn.textContent = '📋 Copy Code'; }, 1500);
        }
    });

    // Toggle Ready button
    toggleReadyBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ready' }));
        }
    });

    // Host Start Game button
    startGameBtn.addEventListener('click', () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'start_game' }));
        }
    });

    // Return to Lobby button
    returnLobbyBtn.addEventListener('click', () => {
        victoryModal.classList.remove('active');
        if (ws) ws.close();
        currentRoom = null;
        switchView('lobby');
        refreshRoomsList();
    });

    function updateHeaderUser(name, avatar) {
        userBadge.style.display = 'flex';
        userNameDisplay.textContent = name;
        userAvatarDisplay.textContent = getAvatarEmoji(avatar);
    }

    function getAvatarEmoji(avatarId) {
        const avatars = {
            'avatar1': '🦊', 'avatar2': '🐺', 'avatar3': '🦁',
            'avatar4': '🐯', 'avatar5': '🐉', 'avatar6': '🤖'
        };
        return avatars[avatarId] || '👤';
    }

    // ---------------- Waiting Room UI ---------------- //
    function showWaitingRoom(room) {
        currentRoom = room;
        waitingRoomCode.textContent = room.code;
        renderWaitingSeats(room);
        switchView('waiting');
    }

    function renderWaitingSeats(room) {
        waitingSeatsGrid.innerHTML = '';
        const isHost = (myPlayerId === room.host_id);

        for (let i = 0; i < room.max_players; i++) {
            const player = room.players[i];
            const seat = document.createElement('div');

            if (player) {
                seat.className = `player-seat occupied ${player.is_ready ? 'is-ready' : ''}`;
                seat.innerHTML = `
                    <div class="seat-avatar">${getAvatarEmoji(player.avatar)}</div>
                    <div class="seat-name">${escapeHtml(player.name)}</div>
                    <span class="seat-tag ${player.is_host ? 'host' : (player.is_ready ? 'ready' : 'not-ready')}">
                        ${player.is_host ? '👑 Host' : (player.is_ready ? '✅ Ready' : '⏳ Waiting')}
                    </span>
                `;
            } else {
                seat.className = 'player-seat';
                seat.innerHTML = `
                    <div class="seat-avatar" style="opacity: 0.2">🪑</div>
                    <div class="seat-name" style="color: #666">Empty Seat</div>
                `;
            }
            waitingSeatsGrid.appendChild(seat);
        }

        // Host controls
        if (isHost) {
            startGameBtn.style.display = 'flex';
            toggleReadyBtn.style.display = 'none';

            const canStart = (room.players.length >= 2 && room.players.every(p => p.is_ready));
            startGameBtn.disabled = !canStart;
            startGameBtn.title = canStart ? "Start Match" : "All players must be ready (min 2 players)";
        } else {
            startGameBtn.style.display = 'none';
            toggleReadyBtn.style.display = 'flex';

            const me = room.players.find(p => p.id === myPlayerId);
            if (me) {
                toggleReadyBtn.textContent = me.is_ready ? '❌ Unready' : '✅ Ready Up';
            }
        }
    }

    // ---------------- WebSocket Handler ---------------- //
    function connectWebSocket(roomCode, playerId) {
        if (ws) {
            ws.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${roomCode}/${playerId}`;

        ws = new WebSocket(wsUrl);

        if (!gameRenderer) {
            gameRenderer = new UnoGameRenderer();
        }
        gameRenderer.setWebSocket(ws, playerId);

        ws.onopen = () => {
            console.log('Connected to UNO No Mercy WebSocket');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWsMessage(data);
            } catch (err) {
                console.error('Error handling WS message:', err);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket closed');
        };

        ws.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }

    function handleWsMessage(data) {
        switch (data.type) {
            case 'room_update':
                currentRoom = data.room;
                if (data.room.status === 'waiting') {
                    renderWaitingSeats(data.room);
                }
                break;

            case 'game_started':
                currentRoom = data.room;
                switchView('game');
                window.sounds.playCard();
                break;

            case 'game_state':
                switchView('game');
                gameRenderer.updateState(data.state);
                break;

            case 'chat_message':
                appendChatMessage(data.message);
                break;

            case 'game_over':
                showVictoryModal(data.winner, data.win_reason, data.duration_seconds);
                break;

            case 'error':
                alert('⚠️ ' + data.message);
                break;
        }
    }

    function appendChatMessage(msg) {
        const item = document.createElement('div');
        item.className = `chat-msg ${msg.is_system ? 'system' : ''}`;
        item.innerHTML = msg.is_system ?
            `<span>${escapeHtml(msg.text)}</span>` :
            `<strong>${escapeHtml(msg.sender_name)}:</strong> ${escapeHtml(msg.text)}`;
        chatMessagesEl.appendChild(item);
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    function showVictoryModal(winner, reason, duration) {
        window.sounds.victory();
        winnerNameEl.textContent = winner ? winner.name : 'Unknown';
        winReasonEl.textContent = reason || 'Victory!';
        victoryModal.classList.add('active');
    }

    async function refreshRoomsList() {
        try {
            const data = await window.API.listRooms();
            activeRoomsList.innerHTML = '';
            if (!data.rooms || data.rooms.length === 0) {
                activeRoomsList.innerHTML = '<div class="room-list-empty">No active rooms found. Create one to play!</div>';
                return;
            }

            data.rooms.forEach(room => {
                const item = document.createElement('div');
                item.className = 'room-item';
                item.innerHTML = `
                    <div>
                        <strong>${escapeHtml(room.host_name)}'s Room</strong>
                        <div style="font-size: 0.8rem; color: #888">Code: ${room.code} • ${room.player_count}/${room.max_players} Players</div>
                    </div>
                    <button class="btn-secondary" style="padding: 6px 14px">Join</button>
                `;
                item.querySelector('button').onclick = () => {
                    joinCodeInput.value = room.code;
                    joinNameInput.focus();
                };
                activeRoomsList.appendChild(item);
            });
        } catch (e) {
            console.error('Failed to list rooms:', e);
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Initial rooms fetch
    refreshRoomsList();
    setInterval(refreshRoomsList, 5000);
});

