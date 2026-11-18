// API Client for UNO Show 'Em No Mercy
const API = {
    async request(endpoint, options = {}) {
        const defaultHeaders = {
            'Content-Type': 'application/json'
        };
        const config = {
            ...options,
            headers: { ...defaultHeaders, ...(options.headers || {}) }
        };
        if (config.body && typeof config.body === 'object') {
            config.body = JSON.stringify(config.body);
        }

        const res = await fetch(endpoint, config);
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || data.error || 'Network request failed');
        }
        return data;
    },

    async login(username, avatar = 'avatar1') {
        return this.request('/api/auth/login', {
            method: 'POST',
            body: { username, avatar }
        });
    },

    async createRoom(host_name, avatar, max_players = 6) {
        return this.request('/api/rooms', {
            method: 'POST',
            body: { host_name, avatar, max_players: parseInt(max_players, 10) }
        });
    },

    async listRooms() {
        return this.request('/api/rooms');
    },

    async getRoom(code) {
        return this.request(`/api/rooms/${code}`);
    },

    async joinRoom(code, player_name, avatar) {
        return this.request(`/api/rooms/${code}/join`, {
            method: 'POST',
            body: { player_name, avatar }
        });
    },

    async getLeaderboard() {
        return this.request('/api/leaderboard');
    },

    async getHistory() {
        return this.request('/api/history');
    }
};

window.API = API;

