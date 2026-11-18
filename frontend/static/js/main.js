// Application Main Coordinator matching unonomercy.in flow

document.addEventListener('DOMContentLoaded', () => {
    let currentUser = null;
    let currentRoom = null;
    let myPlayerId = null;
    let ws = null;
    let gameRenderer = null;

    // View Sections
    const lobbyView = document.getElementById('lobbyView');
    const waitingView = document.getElementById('waitingView');
    const gameView = document.getElementById('gameView');

    // Modals
    const rulebookModal = document.getElementById('rulebookModal');
    const victoryModal = document.getElementById('victoryModal');
    const shareModal = document.getElementById('shareModal');
    const chatDrawer = document.getElementById('chatDrawer');

    // Header buttons
    const rulebookBtn = document.getElementById('rulebookBtn');
    const soundToggleBtn = document.getElementById('soundToggleBtn');
    const chatToggleBtn = document.getElementById('chatToggleBtn');
    const closeRulebookBtn = document.getElementById('closeRulebookBtn');
    const closeChatBtn = document.getElementById('closeChatBtn');
    const onlinePlayerCountEl = document.getElementById('onlinePlayerCountValue');

    // Solo Mode Elements
    const soloPlayBtn = document.getElementById('soloPlayBtn');
    const soloPlayerName = document.getElementById('soloPlayerName');

    // Friends Mode Elements
    const friendsPlayerName = document.getElementById('friendsPlayerName');
    const createFriendsRoomBtn = document.getElementById('createFriendsRoomBtn');
    const joinRoomCodeInput = document.getElementById('joinRoomCodeInput');
    const joinFriendsRoomBtn = document.getElementById('joinFriendsRoomBtn');

    // Matchmaking Elements
    const mmSearchBtn = document.getElementById('mmSearchBtn');
    const mmPlayerName = document.getElementById('mmPlayerName');

    // Waiting Room Elements
    const waitingRoomCode = document.getElementById('waitingRoomCode');
    const waitingPlayerCount = document.getElementById('waitingPlayerCount');
    const waitingSlotsGrid = document.getElementById('waitingSlotsGrid');
    const addAiBtn = document.getElementById('addAiBtn');
    const removeAiBtn = document.getElementById('removeAiBtn');
    const toggleReadyBtn = document.getElementById('toggleReadyBtn');
    const startGameBtn = document.getElementById('startGameBtn');
    const shareRoomBtn = document.getElementById('shareRoomBtn');
    const leaveLobbyBtn = document.getElementById('leaveLobbyBtn');

    // Chat Elements
    const chatMessagesEl = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendChatBtn = document.getElementById('sendChatBtn');

    // Victory Screen
    const winnerNameEl = document.getElementById('winnerNameText');
    const winReasonEl = document.getElementById('winReasonText');
    const rematchBtn = document.getElementById('rematchBtn');
    const returnLobbyBtn = document.getElementById('returnLobbyBtn');

    // Simulated online players counter with realistic fluctuation
    function updateOnlineCount() {
        if (onlinePlayerCountEl) {
            const base = 1420;
            const variance = Math.floor(Math.sin(Date.now() / 10000) * 80) + Math.floor(Math.random() * 15);
            onlinePlayerCountEl.textContent = (base + variance).toLocaleString();
        }
    }
    updateOnlineCount();
    setInterval(updateOnlineCount, 8000);

    function switchView(viewName) {
        [lobbyView, waitingView, gameView].forEach(v => v.classList.remove('active'));
        if (viewName === 'lobby') lobbyView.classList.add('active');
        if (viewName === 'waiting') waitingView.classList.add('active');
        if (viewName === 'game') gameView.classList.add('active');
    }

    // Modal toggles
    if (rulebookBtn) rulebookBtn.onclick = () => rulebookModal.classList.add('active');
    if (closeRulebookBtn) closeRulebookBtn.onclick = () => rulebookModal.classList.remove('active');
    if (chatToggleBtn) chatToggleBtn.onclick = () => chatDrawer.classList.toggle('active');
    if (closeChatBtn) closeChatBtn.onclick = () => chatDrawer.classList.remove('active');

    // Sound toggle
    soundToggleBtn.onclick = () => {
        const enabled = window.sounds.toggle();
        soundToggleBtn.textContent = enabled ? '🔊' : '🔇';
    };

    // Quick emoji reactions
    document.querySelectorAll('.quick-emoji-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const emoji = e.currentTarget.textContent;
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'chatEmoji', emoji: emoji }));
            }
        });
    });

    // Chat send
    function sendChat() {
        const text = chatInput.value.trim();
        if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ type: 'chat', message: text }));
        chatInput.value = '';
    }
    sendChatBtn.onclick = sendChat;
    chatInput.onkeydown = (e) => { if (e.key === 'Enter') sendChat(); };

    // ---------------- 1. SOLO MODE (PLAY WITH BOTS) ---------------- //
    soloPlayBtn.addEventListener('click', async () => {
        const name = soloPlayerName.value.trim() || 'Player';
        try {
            soloPlayBtn.disabled = true;
            soloPlayBtn.textContent = 'Launching...';

            const res = await window.API.request('/api/rooms/solo', {
                method: 'POST',
                body: { host_name: name, avatar: 'avatar1', max_players: 4 }
            });

            myPlayerId = res.host_id;
            currentRoom = res.room;
            currentUser = { name: name, avatar: 'avatar1' };

            connectWebSocket(res.room_code, myPlayerId);
            showWaitingRoom(res.room);
        } catch (err) {
            alert('Failed to launch Solo game: ' + err.message);
        } finally {
            soloPlayBtn.disabled = false;
            soloPlayBtn.textContent = '🤖 Play vs Bots';
        }
    });

    // ---------------- 2. PLAY WITH FRIENDS (CUSTOM ROOM) ---------------- //
    createFriendsRoomBtn.addEventListener('click', async () => {
        const name = friendsPlayerName.value.trim() || 'Host';
        try {
            createFriendsRoomBtn.disabled = true;
            createFriendsRoomBtn.textContent = 'Creating...';

            const res = await window.API.createRoom(name, 'avatar1', 6);
            myPlayerId = res.host_id;
            currentRoom = res.room;
            currentUser = { name: name, avatar: 'avatar1' };

            connectWebSocket(res.room_code, myPlayerId);
            showWaitingRoom(res.room);
        } catch (err) {
            alert('Failed to create room: ' + err.message);
        } finally {
            createFriendsRoomBtn.disabled = false;
            createFriendsRoomBtn.textContent = '👥 Create Room';
        }
    });

    joinFriendsRoomBtn.addEventListener('click', async () => {
        const code = joinRoomCodeInput.value.trim().toUpperCase();
        const name = friendsPlayerName.value.trim() || 'Player';
        if (!code || code.length < 4) {
            alert('Please enter a valid room code.');
            return;
        }

        try {
            joinFriendsRoomBtn.disabled = true;
            joinFriendsRoomBtn.textContent = 'Joining...';

            const res = await window.API.joinRoom(code, name, 'avatar2');
            myPlayerId = res.player_id;
            currentRoom = res.room;
            currentUser = { name: name, avatar: 'avatar2' };

            connectWebSocket(code, myPlayerId);
            showWaitingRoom(res.room);
        } catch (err) {
            alert('Failed to join room: ' + err.message);
        } finally {
            joinFriendsRoomBtn.disabled = false;
            joinFriendsRoomBtn.textContent = 'Join Room';
        }
    });

    // ---------------- 3. QUICK MATCHMAKING ---------------- //
    mmSearchBtn.addEventListener('click', async () => {
        const name = mmPlayerName.value.trim() || 'Player';
        mmSearchBtn.disabled = true;
        mmSearchBtn.textContent = 'Searching...';

        try {
            const listRes = await window.API.listRooms();
            const available = listRes.rooms && listRes.rooms.length > 0 ? listRes.rooms[0] : null;

            if (available) {
                const joinRes = await window.API.joinRoom(available.code, name, 'avatar3');
                myPlayerId = joinRes.player_id;
                currentRoom = joinRes.room;
                connectWebSocket(available.code, myPlayerId);
                showWaitingRoom(joinRes.room);
            } else {
                const createRes = await window.API.createRoom(name, 'avatar3', 4);
                myPlayerId = createRes.host_id;
                currentRoom = createRes.room;
                connectWebSocket(createRes.room_code, myPlayerId);
                showWaitingRoom(createRes.room);
            }
        } catch (err) {
            alert('Matchmaking error: ' + err.message);
        } finally {
            mmSearchBtn.disabled = false;
            mmSearchBtn.textContent = '⚡ Find Match';
        }
    });

    // ---------------- WAITING ROOM CONTROLS ---------------- //
    function showWaitingRoom(room) {
        currentRoom = room;
        waitingRoomCode.textContent = room.code;
        renderWaitingSlots(room);
        switchView('waiting');
    }

    function renderWaitingSlots(room) {
        waitingSlotsGrid.innerHTML = '';
        waitingPlayerCount.textContent = `${room.players.length}/${room.max_players}`;
        const isHost = (myPlayerId === room.host_id);

        for (let i = 0; i < room.max_players; i++) {
            const player = room.players[i];
            const slot = document.createElement('div');

            if (player) {
                slot.className = `player-slot-card occupied ${player.is_ready ? 'is-ready' : ''}`;
                slot.innerHTML = `
                    <div class="slot-avatar">${player.is_ai ? '🤖' : getAvatarEmoji(player.avatar)}</div>
                    <div class="slot-name">${escapeHtml(player.name)}</div>
                    <span class="slot-badge ${player.is_host ? 'host' : (player.is_ai ? 'bot' : (player.is_ready ? 'ready' : 'waiting'))}">
                        ${player.is_host ? '👑 Host' : (player.is_ai ? '🤖 AI Bot' : (player.is_ready ? '✅ Ready' : '⏳ Waiting'))}
                    </span>
                `;

                if (isHost && !player.is_host) {
                    const kickBtn = document.createElement('button');
                    kickBtn.style.position = 'absolute';
                    kickBtn.style.top = '6px';
                    kickBtn.style.right = '8px';
                    kickBtn.style.background = 'none';
                    kickBtn.style.border = 'none';
                    kickBtn.style.color = '#ff1a4b';
                    kickBtn.style.cursor = 'pointer';
                    kickBtn.style.fontSize = '1rem';
                    kickBtn.textContent = '✕';
                    kickBtn.title = 'Remove';
                    kickBtn.onclick = () => {
                        if (player.is_ai) {
                            ws.send(JSON.stringify({ type: 'removeAI', aiId: player.id }));
                        } else {
                            ws.send(JSON.stringify({ type: 'removePlayer', targetId: player.id }));
                        }
                    };
                    slot.appendChild(kickBtn);
                }
            } else {
                slot.className = 'player-slot-card';
                slot.innerHTML = `
                    <div class="slot-avatar" style="opacity: 0.2">🪑</div>
                    <div class="slot-name" style="color: #555">Empty Seat</div>
                `;
            }
            waitingSlotsGrid.appendChild(slot);
        }

        // Host controls
        if (isHost) {
            startGameBtn.style.display = 'block';
            addAiBtn.style.display = 'block';
            removeAiBtn.style.display = 'block';
            toggleReadyBtn.style.display = 'none';

            const canStart = (room.players.length >= 2 && room.players.every(p => p.is_ready));
            startGameBtn.disabled = !canStart;
        } else {
            startGameBtn.style.display = 'none';
            addAiBtn.style.display = 'none';
            removeAiBtn.style.display = 'none';
            toggleReadyBtn.style.display = 'block';

            const me = room.players.find(p => p.id === myPlayerId);
            if (me) {
                toggleReadyBtn.textContent = me.is_ready ? '❌ Unready' : '✅ Ready Up';
            }
        }
    }

    addAiBtn.onclick = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'addAI' }));
        }
    };

    removeAiBtn.onclick = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'removeAI' }));
        }
    };

    toggleReadyBtn.onclick = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ready' }));
        }
    };

    startGameBtn.onclick = () => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'startGame' }));
        }
    };

    shareRoomBtn.onclick = () => {
        if (currentRoom) {
            navigator.clipboard.writeText(currentRoom.code);
            shareRoomBtn.textContent = '✅ Copied!';
            setTimeout(() => { shareRoomBtn.textContent = '📋 Share Code'; }, 1500);
        }
    };

    leaveLobbyBtn.onclick = () => {
        if (ws) ws.close();
        currentRoom = null;
        switchView('lobby');
    };

    // ---------------- WEBSOCKET CONNECTION ---------------- //
    function connectWebSocket(roomCode, playerId) {
        if (ws) ws.close();

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${roomCode}/${playerId}`;

        ws = new WebSocket(wsUrl);

        if (!gameRenderer) {
            gameRenderer = new UnoGameRenderer();
        }
        gameRenderer.setWebSocket(ws, playerId);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWsEvent(data);
            } catch (err) {
                console.error('WS Error:', err);
            }
        };
    }

    function handleWsEvent(data) {
        switch (data.type) {
            case 'room_update':
                currentRoom = data.room;
                if (data.room.status === 'waiting') {
                    renderWaitingSlots(data.room);
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
                appendChat(data.message);
                if (data.emoji) {
                    gameRenderer.spawnFloatingEmoji(data.emoji, data.sender_id);
                }
                break;

            case 'game_over':
                showVictory(data.winner, data.win_reason);
                break;

            case 'error':
                alert('⚠️ ' + data.message);
                break;
        }
    }

    function appendChat(msg) {
        const item = document.createElement('div');
        item.className = `chat-msg ${msg.is_system ? 'system' : ''}`;
        item.innerHTML = msg.is_system ?
            `<span>${escapeHtml(msg.text)}</span>` :
            `<strong>${escapeHtml(msg.sender_name)}:</strong> ${escapeHtml(msg.text)}`;
        chatMessagesEl.appendChild(item);
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    function showVictory(winner, reason) {
        window.sounds.victory();
        winnerNameEl.textContent = winner ? winner.name : 'Unknown';
        winReasonEl.textContent = reason || 'Match Completed!';
        victoryModal.classList.add('active');
    }

    rematchBtn.onclick = () => {
        victoryModal.classList.remove('active');
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'rematch' }));
        }
    };

    returnLobbyBtn.onclick = () => {
        victoryModal.classList.remove('active');
        if (ws) ws.close();
        currentRoom = null;
        switchView('lobby');
    };

    function getAvatarEmoji(avatarId) {
        const avatars = {
            'avatar1': '🦊', 'avatar2': '🐺', 'avatar3': '🦁',
            'avatar4': '🐯', 'avatar5': '🐉', 'avatar6': '🤖'
        };
        return avatars[avatarId] || '👤';
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
});
