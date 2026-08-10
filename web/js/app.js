// CurlingStat Frontend App Logic - Season 2025/2026

let currentView = 'rankings-view';
let currentDiscipline = 'classic_men';
let currentSeason = '2026';
let currentSort = 'fcf_points';
let currentSearch = '';
let currentMatchFilter = 'all'; // 'all', 'group', 'playoff'
let inspectedTournamentData = null;

const API_BASE = '/api';

const DISCIPLINE_INFO = {
  'classic_men': {
    name: 'Мужчины (Классика)',
    desc: '— очки начисляются строго за мужские старты (Чемпионат России Гр. А/Б, Кубок России, ВС)'
  },
  'classic_women': {
    name: 'Женщины (Классика)',
    desc: '— очки начисляются строго за женские старты (Чемпионат России Гр. А/Б, Суперлига, Кубок России, ВС)'
  },
  'juniors_m': {
    name: 'Юниоры (до 22 / до 19 лет)',
    desc: '— очки начисляются строго за молодежные старты (Первенство U22, Первенство U19, Спартакиада)'
  },
  'juniors_w': {
    name: 'Юниорки (до 22 / до 19 лет)',
    desc: '— очки начисляются строго за молодежные старты девушек (Первенство U22, Первенство U19, Спартакиада)'
  },
  'mixed_doubles': {
    name: 'Смешанные пары (Дабл-микст)',
    desc: '— очки начисляются строго за старты смешанных пар (Чемпионат России, Кубок России)'
  },
  'mixed': {
    name: 'Смешанные команды (Микст)',
    desc: '— очки начисляются строго за турниры смешанных четверок (Чемпионат России, Кубок России)'
  },
  'wheelchair': {
    name: 'ПОДА / Кёрлинг на колясках',
    desc: '— очки начисляются строго за соревнования спортсменов с поражением ОДА'
  },
  'wheelchair_mixed_doubles': {
    name: 'ПОДА (Смешанные пары)',
    desc: '— очки начисляются строго за соревнования пар на колясках'
  },
  '': {
    name: 'Все дисциплины',
    desc: '— сводный зачет суммарных очков по всем турнирам сезона'
  }
};

const DISCIPLINE_NAMES = {
  'classic_men': 'Мужчины',
  'classic_women': 'Женщины',
  'mixed': 'Микст',
  'mixed_doubles': 'Дабл-микст',
  'wheelchair': 'ПОДА (Коляски)',
  'wheelchair_mixed_doubles': 'ПОДА См. пары',
  'juniors_m': 'Юниоры U22',
  'juniors_w': 'Юниорки U22',
  'juniors_mixed': 'Юниоры (Пары)',
  'classic_general': 'Общие'
};

document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadSummary();
  updateDisciplineIndicator();
  loadData();
});

function updateDisciplineIndicator() {
  const info = DISCIPLINE_INFO[currentDiscipline] || DISCIPLINE_INFO[''];
  const nameEl = document.getElementById('indicator-discipline-name');
  const descEl = document.getElementById('indicator-discipline-desc');
  if (nameEl && descEl) {
    nameEl.textContent = info.name;
    descEl.textContent = info.desc;
  }
}

function initEventListeners() {
  // Navigation tabs
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const viewId = btn.dataset.view;
      currentView = viewId;
      document.getElementById(viewId).classList.add('active');

      const filterBar = document.getElementById('main-filter-bar');
      const discIndicator = document.getElementById('discipline-indicator');
      
      if (filterBar) filterBar.style.display = 'flex';
      if (discIndicator) {
        discIndicator.style.display = (viewId === 'tournaments-view') ? 'none' : 'flex';
      }

      const titles = {
        'rankings-view': { title: 'Рейтинг игроков', sub: 'Официальные рейтинговые очки ФКР, раздельные зачеты дисциплин и рейтинг Elo' },
        'teams-view': { title: 'Рейтинг команд', sub: 'Совокупная оценка команд, подтвержденные скипы и завоеванные награды' },
        'tournaments-view': { title: 'Все соревнования сезона (21)', sub: 'Протоколы матчей, энд-бай-энд сетки, составы команд и чемпионы' }
      };
      if (titles[viewId]) {
        document.getElementById('page-title').textContent = titles[viewId].title;
        document.getElementById('page-subtitle').textContent = titles[viewId].sub;
      }

      loadData();
    });
  });

  // Discipline tabs
  document.querySelectorAll('.discipline-tabs .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.discipline-tabs .tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDiscipline = btn.dataset.discipline;
      updateDisciplineIndicator();
      loadData();
    });
  });

  // Season filter
  const seasonSelect = document.getElementById('season-filter');
  if (seasonSelect) {
    seasonSelect.addEventListener('change', (e) => {
      currentSeason = e.target.value;
      loadData();
    });
  }

  // Sort filter
  const sortSelect = document.getElementById('sort-filter');
  if (sortSelect) {
    sortSelect.addEventListener('change', (e) => {
      currentSort = e.target.value;
      loadData();
    });
  }

  // Global search with debounce
  let searchTimeout = null;
  const searchInput = document.getElementById('global-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadData();
      }, 300);
    });
  }

  // Modal close handlers
  const tCloseBtn = document.getElementById('modal-close-btn');
  if (tCloseBtn) tCloseBtn.addEventListener('click', closeTournamentModal);
  
  const tModal = document.getElementById('tournament-modal');
  if (tModal) {
    tModal.addEventListener('click', (e) => {
      if (e.target.id === 'tournament-modal') closeTournamentModal();
    });
  }

  const pCloseBtn = document.getElementById('player-modal-close-btn');
  if (pCloseBtn) pCloseBtn.addEventListener('click', closePlayerModal);

  const pModal = document.getElementById('player-modal');
  if (pModal) {
    pModal.addEventListener('click', (e) => {
      if (e.target.id === 'player-modal') closePlayerModal();
    });
  }

  // Modal tabs
  document.querySelectorAll('.modal-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.modal-tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.modal-tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById(btn.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });

  // Global ESC key to close modals
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeTournamentModal();
      closePlayerModal();
    }
  });
}

async function loadSummary() {
  try {
    const res = await fetch(`${API_BASE}/summary`);
    const data = await res.json();
    document.getElementById('stat-tournaments').textContent = (data.total_tournaments || 21).toLocaleString();
    document.getElementById('stat-matches').textContent = (data.total_matches || 1356).toLocaleString();
    document.getElementById('stat-players').textContent = (data.total_players || 649).toLocaleString();
    document.getElementById('stat-ends').textContent = ((data.total_ends || 11115) / 1000).toFixed(1) + 'k';
  } catch (err) {
    console.error("Failed to load summary:", err);
  }
}

function loadData() {
  if (currentView === 'rankings-view') {
    loadPlayerRankings();
  } else if (currentView === 'teams-view') {
    loadTeamRankings();
  } else if (currentView === 'tournaments-view') {
    loadTournaments();
  }
}

async function loadPlayerRankings() {
  const tbody = document.getElementById('rankings-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="loading-cell"><div class="spinner"></div> Загрузка официального рейтинга...</td></tr>';

  try {
    const params = new URLSearchParams();
    if (currentDiscipline) params.append('discipline', currentDiscipline);
    if (currentSeason) params.append('season', currentSeason);
    if (currentSearch) params.append('search', currentSearch);
    if (currentSort) params.append('sort_by', currentSort);
    params.append('limit', '100');

    const res = await fetch(`${API_BASE}/rankings?${params.toString()}`);
    const data = await res.json();

    renderPlayerPodium(data.slice(0, 3));
    renderPlayerRankingsTable(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="error-cell">Ошибка загрузки: ${err.message}</td></tr>`;
  }
}

function renderPlayerPodium(top3) {
  const podium = document.getElementById('player-podium');
  if (!top3 || top3.length === 0) {
    podium.innerHTML = '';
    return;
  }

  const order = [1, 0, 2]; // 2nd, 1st, 3rd
  let html = '';

  order.forEach(idx => {
    if (top3[idx]) {
      const p = top3[idx];
      const rank = idx + 1;
      const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : 'rank-3';
      const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : '🥉';
      
      html += `
        <div class="podium-card glass-card ${rankClass}" onclick="openPlayerProfile(${p.id})">
          <div class="podium-badge">${medal} #${rank}</div>
          <div class="podium-avatar">👤</div>
          <div class="podium-name">${p.full_name}</div>
          <div class="podium-fcf-points">🎖️ ${(p.fcf_points || 0).toFixed(1)} pts</div>
          <div class="podium-rating">⚡ ${Math.round(p.elo_rating)} Elo</div>
          <div class="podium-stats">
            <span>${p.matches_won}W - ${p.matches_lost}L</span>
            <span>${p.win_rate}% побед</span>
          </div>
        </div>
      `;
    }
  });

  podium.innerHTML = html;
}

function renderPlayerRankingsTable(players) {
  const tbody = document.getElementById('rankings-tbody');
  if (!players || players.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Игроки не найдены в выбранной категории</td></tr>';
    return;
  }

  tbody.innerHTML = players.map(p => {
    const rankClass = p.rank <= 3 ? `top-rank rank-${p.rank}` : '';
    const medalsStr = [
      p.gold_medals ? `🥇${p.gold_medals}` : '',
      p.silver_medals ? `🥈${p.silver_medals}` : '',
      p.bronze_medals ? `🥉${p.bronze_medals}` : ''
    ].filter(Boolean).join(' ') || '—';

    return `
      <tr class="${rankClass} clickable-row" onclick="openPlayerProfile(${p.id})">
        <td class="rank-cell"><strong>#${p.rank}</strong></td>
        <td class="player-cell">
          <div class="player-name-link">👤 ${p.full_name}</div>
        </td>
        <td class="points-cell"><span class="fcf-pill">${(p.fcf_points || 0).toFixed(1)}</span></td>
        <td class="elo-cell"><strong>${Math.round(p.elo_rating)}</strong></td>
        <td>${p.matches_played}</td>
        <td class="win-cell">${p.matches_won}</td>
        <td>
          <div class="winrate-bar-container">
            <div class="winrate-bar" style="width: ${p.win_rate}%"></div>
            <span class="winrate-val">${p.win_rate}%</span>
          </div>
        </td>
        <td class="medals-cell">${medalsStr}</td>
        <td>
          <button class="btn-profile" onclick="event.stopPropagation(); openPlayerProfile(${p.id})">Профиль →</button>
        </td>
      </tr>
    `;
  }).join('');
}

async function loadTeamRankings() {
  const tbody = document.getElementById('teams-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="loading-cell"><div class="spinner"></div> Загрузка рейтинга команд...</td></tr>';

  try {
    const params = new URLSearchParams();
    if (currentDiscipline) params.append('discipline', currentDiscipline);
    if (currentSearch) params.append('search', currentSearch);
    params.append('limit', '50');

    const res = await fetch(`${API_BASE}/teams?${params.toString()}`);
    const data = await res.json();

    renderTeamPodium(data.slice(0, 3));
    renderTeamsTable(data);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="9" class="error-cell">Ошибка загрузки: ${err.message}</td></tr>`;
  }
}

function renderTeamPodium(top3) {
  const podium = document.getElementById('team-podium');
  if (!top3 || top3.length === 0) {
    podium.innerHTML = '';
    return;
  }

  const order = [1, 0, 2];
  let html = '';

  order.forEach(idx => {
    if (top3[idx]) {
      const t = top3[idx];
      const rank = idx + 1;
      const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : 'rank-3';
      const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : '🥉';
      
      html += `
        <div class="podium-card glass-card ${rankClass}">
          <div class="podium-badge">${medal} #${rank}</div>
          <div class="podium-avatar">🛡️</div>
          <div class="podium-name">${t.name}</div>
          <div class="podium-skip">👑 ${t.skip_name || 'Скип не указан'}</div>
          <div class="podium-fcf-points">🎖️ ${(t.fcf_points || 0).toFixed(1)} pts</div>
          <div class="podium-stats">
            <span>${t.matches_won}W - ${t.matches_lost}L</span>
            <span>${t.win_rate}% побед</span>
          </div>
        </div>
      `;
    }
  });

  podium.innerHTML = html;
}

function renderTeamsTable(teams) {
  const tbody = document.getElementById('teams-tbody');
  if (!teams || teams.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Команды не найдены в выбранной категории</td></tr>';
    return;
  }

  tbody.innerHTML = teams.map(t => {
    const medalsStr = [
      t.gold_medals ? `🥇${t.gold_medals}` : '',
      t.silver_medals ? `🥈${t.silver_medals}` : '',
      t.bronze_medals ? `🥉${t.bronze_medals}` : ''
    ].filter(Boolean).join(' ') || '—';

    return `
      <tr>
        <td class="rank-cell"><strong>#${t.rank}</strong></td>
        <td><strong>${t.name}</strong></td>
        <td><span class="skip-pill">👑 ${t.skip_name || '—'}</span></td>
        <td class="points-cell"><span class="fcf-pill">${(t.fcf_points || 0).toFixed(1)}</span></td>
        <td class="elo-cell"><strong>${Math.round(t.avg_team_elo)}</strong></td>
        <td>${t.matches_played}</td>
        <td class="win-cell">${t.matches_won}</td>
        <td>
          <div class="winrate-bar-container">
            <div class="winrate-bar" style="width: ${t.win_rate}%"></div>
            <span class="winrate-val">${t.win_rate}%</span>
          </div>
        </td>
        <td class="medals-cell">${medalsStr}</td>
      </tr>
    `;
  }).join('');
}

async function loadTournaments() {
  const grid = document.getElementById('tournaments-grid');
  grid.innerHTML = '<div class="loading-cell"><div class="spinner"></div> Загрузка соревнований сезона 2025/2026...</div>';

  try {
    const params = new URLSearchParams();
    if (currentDiscipline) params.append('discipline', currentDiscipline);
    if (currentSeason) params.append('season', currentSeason);
    if (currentSearch) params.append('search', currentSearch);
    params.append('limit', '50');

    const res = await fetch(`${API_BASE}/tournaments?${params.toString()}`);
    const rawData = await res.json();
    const data = Array.isArray(rawData) ? rawData : (rawData.items || []);

    if (!data || data.length === 0) {
      grid.innerHTML = '<div class="empty-cell">Соревнования не найдены</div>';
      return;
    }

    grid.innerHTML = data.map(t => {
      const tierBadge = t.tier_name ? `<span class="tier-badge-card ${t.tier || 'tier_5_youth_regional'}">${t.tier_name} (${t.base_points || 250} pts)</span>` : '';
      const winnerHtml = t.winner_name ? `
        <div class="winner-row">
          <span class="gold-icon">🥇</span>
          <div class="winner-info">
            <strong>${t.winner_name}</strong>
            ${t.winner_skip ? `<span class="skip-hint">Скип: 👑 ${t.winner_skip}</span>` : ''}
          </div>
        </div>
      ` : '';

      return `
        <div class="tournament-card glass-card" onclick="openTournamentDetails(${t.id})">
          <div class="t-card-header">
            ${tierBadge}
            <span class="t-discipline-tag">${DISCIPLINE_NAMES[t.discipline] || t.discipline}</span>
          </div>
          <h3 class="t-card-title">${t.title}</h3>
          <div class="t-card-dates">📅 ${t.date_display || 'Сезон 2025/2026'}</div>
          
          ${winnerHtml}

          <div class="t-card-footer">
            <div class="t-metric">
              <span class="val">${t.matches_count || 0}</span>
              <span class="lbl">Матчей</span>
            </div>
            <div class="t-metric">
              <span class="val">${t.teams_count || 0}</span>
              <span class="lbl">Команд</span>
            </div>
            <button class="btn-view-t">Табло и Протокол →</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    grid.innerHTML = `<div class="error-cell">Ошибка загрузки турниров: ${err.message}</div>`;
  }
}

async function openTournamentDetails(tournamentId) {
  const modal = document.getElementById('tournament-modal');
  if (!modal) return;
  modal.classList.add('active');

  // Reset tabs to default (matches)
  document.querySelectorAll('.modal-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.modal-tab-panel').forEach(p => p.classList.remove('active'));
  const firstBtn = document.querySelector('.modal-tab-btn[data-tab="tab-matches"]');
  const firstPanel = document.getElementById('tab-matches');
  if (firstBtn) firstBtn.classList.add('active');
  if (firstPanel) firstPanel.classList.add('active');

  document.getElementById('modal-tournament-title').textContent = 'Загрузка турнира...';
  document.getElementById('modal-tournament-meta').textContent = '';
  document.getElementById('modal-matches-list').innerHTML = '<div class="loading-cell"><div class="spinner"></div> Загрузка матчей...</div>';
  document.getElementById('modal-standings-tbody').innerHTML = '';
  document.getElementById('modal-rosters-grid').innerHTML = '';

  try {
    const res = await fetch(`${API_BASE}/tournaments/${tournamentId}`);
    const t = await res.json();
    inspectedTournamentData = t;

    document.getElementById('modal-tournament-title').textContent = t.title;
    document.getElementById('modal-tournament-meta').innerHTML = `
      <span>📅 ${t.date_display || 'Сезон 2025/2026'}</span> • 
      <span class="tier-tag ${t.tier || 'tier_1_championship_a'}">${t.tier_name || 'Чемпионат России'}</span> • 
      <span>🎮 ${t.matches.length} сыгранных матчей</span>
    `;

    renderModalMatches(t.matches, 'all');
    renderModalStandings(t.standings);
    renderModalRosters(t.rosters);

    // Setup match filter buttons inside modal
    document.querySelectorAll('.match-filter-bar .pill-btn').forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.match-filter-bar .pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderModalMatches(t.matches, btn.dataset.filter);
      };
    });

  } catch (err) {
    document.getElementById('modal-tournament-title').textContent = 'Ошибка загрузки данных турнира';
  }
}

function renderModalMatches(matches, filterType) {
  const container = document.getElementById('modal-matches-list');
  if (!matches || matches.length === 0) {
    container.innerHTML = '<div class="empty-cell">Матчи не найдены</div>';
    return;
  }

  let filtered = matches;
  if (filterType === 'playoff') {
    filtered = matches.filter(m => m.stage_type === 'playoff' || (m.tour_name && (m.tour_name.toLowerCase().includes('финал') || m.tour_name.toLowerCase().includes('1/2') || m.tour_name.toLowerCase().includes('1/4') || m.tour_name.toLowerCase().includes('плей-офф'))));
  } else if (filterType === 'group') {
    filtered = matches.filter(m => m.stage_type !== 'playoff' && (!m.tour_name || (!m.tour_name.toLowerCase().includes('финал') && !m.tour_name.toLowerCase().includes('плей-офф'))));
  }

  if (filtered.length === 0) {
    container.innerHTML = '<div class="empty-cell">В этой стадии матчи отсутствуют</div>';
    return;
  }

  // Group by tour_name
  const grouped = {};
  filtered.forEach(m => {
    const tour = m.tour_name || 'Матчи';
    if (!grouped[tour]) grouped[tour] = [];
    grouped[tour].push(m);
  });

  let html = '';
  for (const [tour, tMatches] of Object.entries(grouped)) {
    html += `<div class="tour-block-header">${tour}</div>`;
    tMatches.forEach(m => {
      const isPlayoff = m.stage_type === 'playoff' || (m.tour_name && m.tour_name.toLowerCase().includes('финал'));
      const cardClass = isPlayoff ? 'match-card playoff-card' : 'match-card';
      
      const t1Winner = m.winner_name === m.team1_name ? 'winner-team' : '';
      const t2Winner = m.winner_name === m.team2_name ? 'winner-team' : '';

      let endsHeader = '';
      let endsRow1 = '';
      let endsRow2 = '';

      if (m.ends && m.ends.length > 0) {
        endsHeader = m.ends.map(e => `<th>${e.end_number}</th>`).join('');
        endsRow1 = m.ends.map(e => `<td>${e.team1_score}</td>`).join('');
        endsRow2 = m.ends.map(e => `<td>${e.team2_score}</td>`).join('');
      }

      html += `
        <div class="${cardClass}">
          <div class="match-scoreboard-table-wrapper">
            <table class="end-scoreboard">
              <thead>
                <tr>
                  <th class="team-col-header">Команда (Скип)</th>
                  <th class="hammer-col">🔨</th>
                  ${endsHeader}
                  <th class="total-col">ИТОГО</th>
                </tr>
              </thead>
              <tbody>
                <tr class="${t1Winner}">
                  <td class="team-title-cell">
                    <strong>${m.team1_name}</strong>
                    ${m.team1_skip ? `<span class="match-skip-tag">(${m.team1_skip})</span>` : ''}
                  </td>
                  <td class="hammer-cell">${m.team1_hammer_start ? '🔨' : ''}</td>
                  ${endsRow1}
                  <td class="total-cell"><strong>${m.team1_total_score ?? '—'}</strong></td>
                </tr>
                <tr class="${t2Winner}">
                  <td class="team-title-cell">
                    <strong>${m.team2_name}</strong>
                    ${m.team2_skip ? `<span class="match-skip-tag">(${m.team2_skip})</span>` : ''}
                  </td>
                  <td class="hammer-cell">${m.team2_hammer_start ? '🔨' : ''}</td>
                  ${endsRow2}
                  <td class="total-cell"><strong>${m.team2_total_score ?? '—'}</strong></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
}

function renderModalStandings(standings) {
  const tbody = document.getElementById('modal-standings-tbody');
  if (!standings || standings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Протокол мест не сформирован</td></tr>';
    return;
  }

  tbody.innerHTML = standings.map(st => {
    const medal = st.place === 1 ? '🥇 1 место' : st.place === 2 ? '🥈 2 место' : st.place === 3 ? '🥉 3 место' : `#${st.place}`;
    const medalClass = st.place <= 3 ? `podium-place place-${st.place}` : '';
    
    // Make roster player names clickable
    let rosterHtml = '—';
    if (st.roster_players && st.roster_players.length > 0) {
      rosterHtml = st.roster_players.map(pName => {
        return `<span class="roster-player-name-link" onclick="searchAndOpenPlayer('${pName}')">${pName}</span>`;
      }).join(', ');
    }

    return `
      <tr class="${medalClass}">
        <td class="place-col"><strong>${medal}</strong></td>
        <td><strong>${st.team_name}</strong></td>
        <td><span class="skip-pill">👑 ${st.skip_name || '—'}</span></td>
        <td class="roster-cell">${rosterHtml}</td>
        <td class="coach-cell">${st.coach || '—'}</td>
      </tr>
    `;
  }).join('');
}

function renderModalRosters(rosters) {
  const grid = document.getElementById('modal-rosters-grid');
  if (!rosters || rosters.length === 0) {
    grid.innerHTML = '<div class="empty-cell">Составы команд отсутствуют</div>';
    return;
  }

  grid.innerHTML = rosters.map(r => {
    const playersHtml = (r.players || []).map(p => {
      const isSkip = p.role === 'skip' || (r.skip && p.name.includes(r.skip.split(' ')[0]));
      return `
        <li class="${isSkip ? 'skip-player-item' : ''}" onclick="searchAndOpenPlayer('${p.name}')">
          <span class="p-role-icon">${isSkip ? '👑' : '•'}</span>
          <span class="p-player-name player-click-link">${p.name}</span>
          ${isSkip ? '<span class="skip-badge-tag">Скип</span>' : ''}
        </li>
      `;
    }).join('');

    return `
      <div class="roster-card glass-card">
        <div class="roster-card-header">
          <h4>${r.team_name}</h4>
          ${r.skip ? `<div class="roster-skip-line">Скип: <strong>${r.skip}</strong></div>` : ''}
        </div>
        <ul class="roster-players-list">
          ${playersHtml}
        </ul>
        ${r.coach ? `<div class="roster-coach-line">Тренеры: ${r.coach}</div>` : ''}
      </div>
    `;
  }).join('');
}

async function searchAndOpenPlayer(name) {
  if (!name) return;
  try {
    const cleanName = name.replace(/[^А-Яа-яA-Za-z\s]/g, '').trim();
    const res = await fetch(`${API_BASE}/rankings?search=${encodeURIComponent(cleanName)}&limit=1`);
    const data = await res.json();
    if (data && data.length > 0) {
      openPlayerProfile(data[0].id);
    }
  } catch (e) {
    console.error("Search player failed:", e);
  }
}

function closeTournamentModal() {
  const m = document.getElementById('tournament-modal');
  if (m) m.classList.remove('active');
}

async function openPlayerProfile(playerId) {
  const modal = document.getElementById('player-modal');
  if (!modal) return;
  modal.classList.add('active');

  document.getElementById('pm-name').textContent = 'Загрузка профиля...';
  document.getElementById('pm-meta').textContent = '';
  document.getElementById('pm-fcf-points').textContent = '0.0';
  document.getElementById('pm-rating').textContent = '—';
  document.getElementById('pm-winrate').textContent = '—';
  document.getElementById('pm-medals').textContent = '—';
  document.getElementById('pm-discipline-breakdown').innerHTML = '<div class="spinner"></div>';
  document.getElementById('pm-tournaments-list').innerHTML = '';

  try {
    const res = await fetch(`${API_BASE}/players/${playerId}`);
    const p = await res.json();

    document.getElementById('pm-name').textContent = p.full_name;
    document.getElementById('pm-meta').textContent = `${p.gender === 'F' ? 'Женский зачет' : 'Мужской зачет'} • Сезон 2025/2026`;
    document.getElementById('pm-fcf-points').textContent = (p.fcf_points || 0).toFixed(1);
    document.getElementById('pm-rating').textContent = `${Math.round(p.elo_rating)} Elo`;
    document.getElementById('pm-winrate').textContent = `${p.win_rate}% (${p.matches_won}W - ${p.matches_lost}L)`;
    
    document.getElementById('pm-medals').innerHTML = `
      <span>🥇 ${p.gold_medals || 0}</span>
      <span>🥈 ${p.silver_medals || 0}</span>
      <span>🥉 ${p.bronze_medals || 0}</span>
    `;

    // Render isolated discipline breakdown chips
    const discGrid = document.getElementById('pm-discipline-breakdown');
    if (p.discipline_breakdown && p.discipline_breakdown.length > 0) {
      discGrid.innerHTML = p.discipline_breakdown.map(d => {
        const dName = DISCIPLINE_NAMES[d.discipline] || d.discipline;
        const medals = [
          d.gold_medals ? `🥇${d.gold_medals}` : '',
          d.silver_medals ? `🥈${d.silver_medals}` : '',
          d.bronze_medals ? `🥉${d.bronze_medals}` : ''
        ].filter(Boolean).join(' ');

        return `
          <div class="discipline-breakdown-chip">
            <div class="chip-header">
              <span class="chip-title">${dName}</span>
              <span class="chip-points">🎖️ ${(d.fcf_points || 0).toFixed(1)} pts</span>
            </div>
            <div class="chip-stats">
              <span>${d.matches_played} матчей (W:${d.matches_won} L:${d.matches_lost})</span>
              <span>${d.win_rate}% побед</span>
              ${medals ? `<span class="chip-medals">${medals}</span>` : ''}
            </div>
          </div>
        `;
      }).join('');
    } else {
      discGrid.innerHTML = '<div class="empty-cell">Статистика по категориям отсутствует</div>';
    }

    // Render played tournaments list
    const tournList = document.getElementById('pm-tournaments-list');
    if (p.tournaments && p.tournaments.length > 0) {
      tournList.innerHTML = p.tournaments.map(tr => {
        const placeStr = tr.final_place ? (tr.final_place === 1 ? '🥇 1 место' : tr.final_place === 2 ? '🥈 2 место' : tr.final_place === 3 ? '🥉 3 место' : `#${tr.final_place} место`) : 'Участие';
        const roleStr = tr.role === 'skip' ? '<span class="skip-badge-tag">Скип 👑</span>' : '<span class="player-badge-tag">Игрок</span>';

        return `
          <div class="player-tourn-row" onclick="openTournamentDetails(${tr.tournament_id})">
            <div class="pt-info">
              <strong>${tr.title}</strong>
              <div class="pt-sub">
                <span>🛡️ ${tr.team_name}</span> • 
                ${roleStr} • 
                <span class="tier-tag ${tr.tier || ''}">${tr.tier_name || 'Турнир'}</span>
              </div>
            </div>
            <div class="pt-place">
              <span class="place-badge">${placeStr}</span>
            </div>
          </div>
        `;
      }).join('');
    } else {
      tournList.innerHTML = '<div class="empty-cell">Турниры не найдены</div>';
    }

  } catch (err) {
    document.getElementById('pm-name').textContent = 'Ошибка загрузки профиля игрока';
  }
}

function closePlayerModal() {
  const m = document.getElementById('player-modal');
  if (m) m.classList.remove('active');
}
