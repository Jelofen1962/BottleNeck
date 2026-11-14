/* BottleNeck v0.6.0
   Creator credit requested by the project owner: «ساخته شده با عشق توسط ژلوفن».
   Telegram: https://t.me/jelofen1962 | Phone: +989109721962
*/
(() => {
  'use strict';
  const VERSION = '0.6.0';
  const STATUSES = [
    { id: 'todo', label: 'در صف', cls: 'todo' },
    { id: 'in-progress', label: 'در حال انجام', cls: 'in-progress' },
    { id: 'review', label: 'در بررسی', cls: 'review' },
    { id: 'blocked', label: 'متوقف‌شده', cls: 'blocked' },
    { id: 'done', label: 'تکمیل‌شده', cls: 'done' }
  ];
  const PRIORITIES = [
    { id: 'urgent', label: 'فوری', cls: 'urgent' },
    { id: 'high', label: 'زیاد', cls: 'high' },
    { id: 'medium', label: 'متوسط', cls: 'medium' },
    { id: 'low', label: 'کم', cls: 'low' }
  ];
  const PAGES = {
    overview: 'نمای کلی', 'my-tasks': 'کارهای من', 'all-tasks': 'همه کارها',
    board: 'برد کانبان', calendar: 'تقویم', projects: 'پروژه‌ها',
    teams: 'تیم‌ها و اعضا', activity: 'گزارش فعالیت', reports: 'گزارش‌های عملکرد',
    approvals: 'درخواست‌های تأیید', recurring: 'کارهای تکرارشونده', templates: 'قالب‌های کار',
    handbook: 'راهنمای استفاده', settings: 'تنظیمات', 'shared-board':'برد ایده‌های مشترک', 'shared-drive':'فایل‌ها و پوشه‌ها', 'shared-notes':'یادداشت‌های Markdown', 'team-chat':'گفت‌وگوی تیمی'
  };
  const TOUR = [
    ['نمای کلی', 'این صفحه نبض فضای کاری را نشان می‌دهد: تعداد کارها، کارهای در جریان، موعدهای نزدیک، فعالیت‌های تازه و توزیع مسئولیت‌ها. آمار فقط از داده‌های واقعی فضای شما ساخته می‌شود.'],
    ['کارها', 'از «کار جدید» برای ثبت یک خروجی روشن استفاده کنید. می‌توانید چند مسئول، تیم، پروژه، اولویت، زمان برآوردی و موعد انجام انتخاب کنید.'],
    ['چک‌لیست و پیوست', 'داخل جزئیات هر کار، چک‌لیست بسازید، فایل پیوست کنید و در بخش گفتگو با همکاران هماهنگ شوید. محدودیت هر فایل ۱۰ مگابایت است.'],
    ['برد کانبان', 'کارت‌ها را بین ستون‌ها بکشید. تغییر وضعیت به سرور ذخیره می‌شود و همکاران در شبکه محلی تغییر را دریافت می‌کنند.'],
    ['تقویم و پروژه‌ها', 'موعد کارها را در تقویم ببینید و کارهای مرتبط را در پروژه‌ها جمع کنید. پیشرفت پروژه از کارهای متصل محاسبه می‌شود.'],
    ['تیم‌ها و اعلان‌ها', 'اعضا را به تیم‌ها اضافه کنید، برای همکاران لینک دعوت بسازید و اعلان‌های واگذاری یا گفتگو را از زنگوله بالا بررسی کنید.'],
    ['زمان‌سنج و گزارش‌ها', 'برای هر کار زمان‌سنج را شروع و متوقف کنید. گزارش‌های روزانه و هفتگی، زمان صرف‌شده و کارهای انجام‌شده را جمع‌بندی می‌کنند.'],
    ['قالب و تکرار', 'از قالب‌ها برای کارهای مشابه استفاده کنید و کارهای روزانه، هفتگی یا ماهانه را به‌صورت خودکار بسازید.'],
    ['بازبینی و پیش‌نیازها', 'پیش‌نیازها مانع تکمیل زودهنگام کار می‌شوند. وقتی خروجی آماده است، درخواست تأیید بفرستید تا مدیر آن را بررسی کند.'],
    ['فضای مشترک و برد ایده‌ها', 'در برد مشترک ایده‌ها را روی بوم آزاد بچینید؛ فایل‌ها، پوشه‌ها و یادداشت‌های Markdown را با سطح دسترسی تیم یا گذرواژه به اشتراک بگذارید. گفت‌وگوی تیمی برای هماهنگی سریع در دسترس است.'],
    ['راهنما و پشتیبان‌گیری', 'راهنمای کامل داخل برنامه قرار دارد. پایگاه داده و فایل‌ها روی رایانه میزبان ذخیره می‌شوند؛ به‌طور منظم از پوشه data پشتیبان بگیرید.']
  ];
  const $ = (id) => document.getElementById(id);
  const state = { me: null, tasks: [], users: [], teams: [], projects: [], activity: [], invitations: [], notifications: [],
    recurringRules: [], templates: [], statusLabels: [], pendingApprovals: [], activeTimer: null,
    reportData: null, reportPeriod: 'weekly', unread: 0, page: 'overview', search: '', eventCursor: 0,
    pollHandle: null, month: new Date(), taskFilter: 'all', modalTaskId: null, tourStep: 0, network: null,
    boards: [], activeBoardId: null, boardItems: [], boardPassword: '', driveItems: [], driveParentId: null, driveTrail: [], drivePassword: '',
    chatMessages: [], chatChannel: 'workspace', chatTeamId: '', chatPresence: [], presenceHandle: null, uploadShareSettings: null,
    workspaces: [], rolePermissions: [], backups: [], security: null, notificationPrefs: null, ws: null, wsReconnectTimer: null, pauseSocketReconnect: false };

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const faNum = (value) => Number(value || 0).toLocaleString('fa-IR');
  const roleLabel = (r) => ({ owner: 'مالک', admin: 'مدیر', member: 'عضو' }[r] || 'عضو');
  const statusOf = (id) => { const base=STATUSES.find(x => x.id === id) || STATUSES[0]; const custom=(state.statusLabels||[]).find(x=>x.key===base.id); return custom ? {...base,label:custom.label,color:custom.color} : base; };
  const priorityOf = (id) => PRIORITIES.find(x => x.id === id) || PRIORITIES[2];
  const userOf = (id) => state.users.find(u => u.id === id) || { id: '', name: 'بدون مسئول', email: '', role: 'member' };
  const projectOf = (id) => state.projects.find(p => p.id === id) || { name: 'بدون پروژه' };
  const teamOf = (id) => state.teams.find(t => t.id === id) || { name: 'بدون تیم' };
  const isAdmin = () => state.me && (state.me.canManage || ['owner', 'admin'].includes(state.me.role));
  const isOwner = () => state.me && state.me.role === 'owner';
  const fmtDate = (iso, options = { day: 'numeric', month: 'short' }) => {
    if (!iso) return 'بدون موعد';
    const dt = new Date(`${iso.slice(0, 10)}T12:00:00`);
    return Number.isNaN(dt.getTime()) ? iso : dt.toLocaleDateString('fa-IR', options);
  };
  const fmtTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleString('fa-IR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  };
  const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
  const overdue = (task) => task.status !== 'done' && task.dueDate && task.dueDate < todayISO();
  const initials = (name) => String(name || '؟').trim().split(/\s+/).slice(0, 2).map(x => x[0] || '').join('') || '؟';
  const avatar = (user, size = '') => `<span class="avatar ${size}" title="${esc(user?.name || '')}">${esc(initials(user?.name))}</span>`;
  const avatarStack = (arr = []) => `<span class="avatar-stack">${arr.slice(0, 4).map(x => avatar(x, 'avatar-xs')).join('')}${arr.length > 4 ? `<span class="avatar avatar-xs">+${faNum(arr.length - 4)}</span>` : ''}</span>`;
  const statusPill = (id) => { const s = statusOf(id); return `<span class="status-pill status-${s.cls} status-tint-${esc(s.color||'neutral')}">${esc(s.label)}</span>`; };
  const priorityPill = (id) => { const p = priorityOf(id); return `<span class="priority-pill priority-${p.cls}">${p.label}</span>`; };
  const empty = (icon, title, message) => `<div class="empty-state"><i data-lucide="${icon}"></i><strong>${esc(title)}</strong><br>${esc(message)}</div>`;
  const rolePill = (role) => `<span class="role-pill ${role === 'owner' ? 'owner' : ''}">${roleLabel(role)}</span>`;
  const iconRefresh = () => { try { window.lucide?.createIcons?.(); } catch (_) {} };

  async function api(path, options = {}) {
    const opts = { credentials: 'same-origin', ...options, headers: { ...(options.headers || {}) } };
    if (opts.body && !(opts.body instanceof Blob) && !(opts.body instanceof ArrayBuffer) && typeof opts.body !== 'string') {
      opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(opts.body);
    }
    const response = await fetch(path, opts);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) {
      if (response.status === 401 && path !== '/api/auth/login' && path !== '/api/auth/register') showAuth();
      const detail = payload && typeof payload === 'object' ? payload.detail : payload;
      throw new Error(detail || `درخواست ناموفق بود (${response.status})`);
    }
    return payload;
  }
  function toast(message, icon = 'check') {
    const node = document.createElement('div'); node.className = 'toast';
    node.innerHTML = `<i data-lucide="${esc(icon)}"></i><span>${esc(message)}</span>`;
    $('toastRegion').appendChild(node); iconRefresh();
    window.setTimeout(() => { node.style.opacity = '0'; node.style.transform = 'translateY(7px)'; window.setTimeout(() => node.remove(), 220); }, 2900);
  }
  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(value); return true; } catch (_) { /* fall through to legacy copy for HTTP LAN */ }
    }
    const area = document.createElement('textarea'); area.value = value; area.setAttribute('readonly','');
    area.style.position = 'fixed'; area.style.opacity = '0'; area.style.pointerEvents = 'none';
    document.body.appendChild(area); area.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (_) { ok = false; }
    area.remove();
    if (!ok) throw new Error('کپی خودکار در این مرورگر مجاز نیست؛ نشانی را دستی انتخاب و کپی کنید.');
    return true;
  }

  function setAuthTab(tab) {
    document.querySelectorAll('[data-auth-tab]').forEach(b => b.classList.toggle('active', b.dataset.authTab === tab));
    $('loginPanel').classList.toggle('hidden', tab !== 'login');
    $('registerPanel').classList.toggle('hidden', tab !== 'register');
    $('authError').classList.add('hidden');
  }
  function showAuth() {
    state.me = null;
    stopPolling(); $('appShell').classList.add('hidden'); $('authScreen').classList.remove('hidden');
    setAuthTab(new URLSearchParams(location.search).has('invite') ? 'register' : 'login');
  }
  async function signIn(form) {
    const email = $('loginEmail').value.trim(); const password = $('loginPassword').value;
    try {
      const result = await api('/api/auth/login', { method: 'POST', body: { email, password } });
      if (result.twoFactorRequired) {
        const code = prompt('کد ۶ رقمی برنامه احراز هویت یا یکی از کدهای بازیابی را وارد کنید:');
        if (!code) return;
        await api('/api/auth/2fa/verify', { method:'POST', headers:{'X-Login-Challenge':result.challengeToken}, body:{code:code.trim()} });
      }
      const invite = new URLSearchParams(location.search).get('invite');
      if (invite) {
        await api(`/api/invitations/${encodeURIComponent(invite)}/accept`, {method:'POST'});
        history.replaceState({}, '', location.pathname);
      }
      await startWorkspace();
    } catch (e) { showAuthError(e.message); }
  }
  async function register(form) {
    const invite = new URLSearchParams(location.search).get('invite') || '';
    const body = { name: $('registerName').value.trim(), email: $('registerEmail').value.trim(), password: $('registerPassword').value,
      workspace_name: $('workspaceName').value.trim(), invite_code: invite || null };
    try { await api('/api/auth/register', { method: 'POST', body }); history.replaceState({}, '', location.pathname); await startWorkspace(true); }
    catch (e) { showAuthError(e.message); }
  }
  function showAuthError(message) { $('authError').textContent = message; $('authError').classList.remove('hidden'); }

  async function startWorkspace(isNew = false) {
    try {
      const data = await api('/api/bootstrap');
      Object.assign(state, data); state.unread = Number(data.unreadNotifications || 0); state.eventCursor = Number(data.eventCursor || 0); state.workspaces = data.workspaces || [];
      $('authScreen').classList.add('hidden'); $('appShell').classList.remove('hidden');
      $('workspaceNameLabel').textContent = state.me.workspaceName;
      $('workspaceInitial').textContent = initials(state.me.workspaceName).slice(0, 1);
      $('workspaceRoleLabel').textContent = `${roleLabel(state.me.role)} · فضای مشترک`;
      populateWorkspaceSelector();
      $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role);
      $('profileAvatar').textContent = initials(state.me.name).slice(0, 1); $('welcomeName')?.textContent;
      $('globalSearch').value = state.search;
      $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role); $('profileAvatar').textContent = initials(state.me.name).slice(0, 1);
      render(); startPolling();
      const sharedTarget=new URLSearchParams(location.search).get('openNode'); if(sharedTarget){history.replaceState({},'',location.pathname);state.page='shared-drive';render();await loadDrive(null);await openDriveNode(sharedTarget);}
      if (!state.me.onboardingCompleted) openTour();
      else if (isNew) toast('حساب شما آماده است. به BottleNeck خوش آمدید.');
    } catch (e) { showAuth(); if (isNew) showAuthError(e.message); }
  }
  async function refreshWorkspace(quiet = false) {
    const data = await api('/api/bootstrap');
    Object.assign(state, data); state.unread = Number(data.unreadNotifications || 0); state.eventCursor = Math.max(state.eventCursor, Number(data.eventCursor || 0)); state.workspaces = data.workspaces || state.workspaces;
    populateWorkspaceSelector();
    $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role); $('profileAvatar').textContent = initials(state.me.name).slice(0, 1);
    render();
    if (!quiet) toast('فضای کار به‌روز شد.');
  }
  async function handleLiveEvents(result) {
    const events = result.events || [];
    state.eventCursor = Math.max(state.eventCursor, Number(result.cursor || 0));
    const external = events.filter(e => e.user_id && e.user_id !== state.me.id);
    if (!events.length) return;
    const before = state.unread;
    const data = await api('/api/bootstrap');
    Object.assign(state, data); state.workspaces = data.workspaces || state.workspaces;
    state.unread = Number(data.unreadNotifications || 0);
    state.eventCursor = Math.max(state.eventCursor, Number(data.eventCursor || 0));
    populateWorkspaceSelector(); render(); reloadLivePage();
    if (external.length) toast('به‌روزرسانی زنده از هم‌تیمی‌ها دریافت شد.', 'refresh-cw');
    if (state.unread > before || Number(result.unread || 0) > before) toast('اعلان تازه دارید.', 'bell');
  }
  function connectLiveSocket() {
    if (!state.me || !('WebSocket' in window)) return;
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/ws?after_id=${state.eventCursor}`);
    state.ws = socket;
    socket.onmessage = event => { try { handleLiveEvents(JSON.parse(event.data)); } catch (_) {} };
    socket.onclose = () => {
      if (state.me && !state.pauseSocketReconnect && !state.wsReconnectTimer) state.wsReconnectTimer = window.setTimeout(() => { state.wsReconnectTimer = null; connectLiveSocket(); }, 1800);
    };
    socket.onerror = () => { try { socket.close(); } catch (_) {} };
  }
  function startPolling() {
    stopPolling(); state.pauseSocketReconnect=false; connectLiveSocket();
    if (state.presenceHandle) window.clearInterval(state.presenceHandle);
    api('/api/presence',{method:'POST',body:{page:state.page}}).catch(()=>{});
    state.presenceHandle = window.setInterval(()=>api('/api/presence',{method:'POST',body:{page:state.page}}).catch(()=>{}),12000);
  }
  function stopPolling() {
    state.pauseSocketReconnect=true;
    if (state.pollHandle) window.clearInterval(state.pollHandle);
    if(state.presenceHandle)window.clearInterval(state.presenceHandle);
    if(state.wsReconnectTimer){clearTimeout(state.wsReconnectTimer);state.wsReconnectTimer=null;}
    if(state.ws){const old=state.ws;state.ws=null;try{old.close();}catch(_){}}
    state.pollHandle = null; state.presenceHandle=null;
  }

  function populateWorkspaceSelector() {
    const select = $('workspaceSelect'); if(!select) return;
    const current = state.me?.workspaceId || '';
    select.innerHTML = `${(state.workspaces||[]).map(w=>`<option value="${esc(w.id)}" ${w.id===current?'selected':''}>${esc(w.name)} · ${roleLabel(w.role)}</option>`).join('')}<option value="__new__">＋ فضای کاری تازه</option>`;
  }
  async function switchWorkspaceOrCreate(value) {
    try {
      let target = value;
      if(value==='__new__'){
        const name = prompt('نام فضای کاری تازه را وارد کنید:');
        if(!name || name.trim().length<2){populateWorkspaceSelector();return;}
        const created = await api('/api/workspaces',{method:'POST',body:{name:name.trim()}}); target=created.id;
      }
      if(!target || target===state.me.workspaceId){populateWorkspaceSelector();return;}
      await api('/api/workspaces/switch',{method:'POST',body:{workspace_id:target}});
      state.page='overview'; stopPolling(); await startWorkspace(); toast('فضای کاری تغییر کرد.','repeat');
    }catch(e){populateWorkspaceSelector();toast(e.message,'alert-circle');}
  }

  function showModal(title, body, eyebrow = 'BottleNeck') {
    $('modalTitle').textContent = title; $('modalEyebrow').textContent = eyebrow; $('modalBody').innerHTML = body;
    $('modalBackdrop').classList.add('open'); $('modalBackdrop').setAttribute('aria-hidden', 'false'); document.body.style.overflow = 'hidden'; iconRefresh();
  }
  function closeModal() { $('modalBackdrop').classList.remove('open'); $('modalBackdrop').setAttribute('aria-hidden', 'true'); $('modalBody').innerHTML = ''; document.body.style.overflow = ''; state.modalTaskId = null; }
  function closeCredit() { $('creditBackdrop').classList.remove('open'); $('creditBackdrop').setAttribute('aria-hidden', 'true'); }
  function openCredit() { $('creditBackdrop').classList.add('open'); $('creditBackdrop').setAttribute('aria-hidden', 'false'); iconRefresh(); }

  function heading(title, description, action = '') {
    return `<div class="page-heading"><div><p class="eyebrow"><span class="live-dot"></span> فضای کاری ${esc(state.me.workspaceName)}</p><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="heading-actions">${action}</div></div>`;
  }
  function tasksFiltered(onlyMine = false) {
    const q = state.search.trim().toLocaleLowerCase('fa');
    return state.tasks.filter(t => {
      if (onlyMine && !(t.assigneeIds || []).includes(state.me.id)) return false;
      if (!q) return true;
      const users = (t.assignees || []).map(a => a.name).join(' ');
      return [t.title, t.description, users, t.teamName, t.projectName].join(' ').toLocaleLowerCase('fa').includes(q);
    });
  }
  function render() {
    $('breadcrumbCurrent').textContent = PAGES[state.page] || 'نمای کلی';
    document.querySelectorAll('.nav-item[data-page]').forEach(b => b.classList.toggle('active', b.dataset.page === state.page));
    $('myTaskCount').textContent = faNum(state.tasks.filter(t => (t.assigneeIds || []).includes(state.me.id) && t.status !== 'done').length);
    $('notificationDot').classList.toggle('hidden', state.unread < 1);
    const approvalCount=$('approvalCount'); if(approvalCount) approvalCount.textContent=faNum((state.pendingApprovals||[]).filter(a=>a.status==='pending').length);
    const renderer = {
      overview: renderOverview, 'my-tasks': () => renderTasks(true), 'all-tasks': () => renderTasks(false),
      board: renderBoard, calendar: renderCalendar, projects: renderProjects, teams: renderTeams,
      activity: renderActivity, reports: renderReports, approvals: renderApprovals,
      recurring: renderRecurring, templates: renderTemplates, handbook: renderHandbook, settings: renderSettings,
      'shared-board': renderSharedBoard, 'shared-drive': renderSharedDrive, 'shared-notes': renderSharedNotes, 'team-chat': renderTeamChat
    }[state.page] || renderOverview;
    $('pageContent').innerHTML = renderer(); iconRefresh();
  }
  function teamOptions(selected = '') {
    return state.teams.map(t => `<option value="${esc(t.id)}" ${selected===t.id?'selected':''}>${esc(t.name)}</option>`).join('');
  }
  function shareControls(prefix = 'share') {
    return `<label class="field"><span>نحوه دسترسی</span><select name="access_mode" id="${prefix}Access"><option value="workspace">همه اعضای فضای کاری</option><option value="team">فقط یک تیم مشخص</option><option value="password">محافظت با گذرواژه</option></select></label>
      <label class="field hidden" id="${prefix}TeamWrap"><span>تیم مجاز</span><select name="team_id">${teamOptions()}</select></label>
      <label class="field hidden" id="${prefix}PasswordWrap"><span>گذرواژه اشتراک (حداقل ۸ نویسه)</span><input type="password" name="password" minlength="8" autocomplete="new-password" /></label>`;
  }
  async function loadBoards() {
    state.boards = await api('/api/boards');
    if (!state.activeBoardId || !state.boards.some(b=>b.id===state.activeBoardId)) state.activeBoardId = state.boards[0]?.id || null;
    if (state.activeBoardId) await loadBoardItems(); else { state.boardItems=[]; render(); }
  }
  async function loadBoardItems(password = state.boardPassword) {
    if (!state.activeBoardId) return;
    const suffix = password ? `?password=${encodeURIComponent(password)}` : '';
    try {
      const data = await api(`/api/boards/${state.activeBoardId}/items${suffix}`);
      state.boardItems = data.items || []; state.boardPassword = password || ''; state.activeBoard = data.board; render();
    } catch (e) {
      if (e.message.includes('گذرواژه')) {
        const pass = prompt('این برد با گذرواژه محافظت شده است. گذرواژه را وارد کنید:');
        if (pass) return loadBoardItems(pass);
      }
      toast(e.message,'lock');
    }
  }
  function renderSharedBoard() {
    const active = state.boards.find(b=>b.id===state.activeBoardId);
    const cards = state.boardItems.map(item => {
      const color = ['butter','rose','sage','blue','paper'].includes(item.color)?item.color:'butter';
      const body = item.type==='link' ? `<a class="board-link" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.url)}</a>` : item.type==='task' ? `<p>${esc(state.tasks.find(t=>t.id===item.taskId)?.title || item.title || 'کار متصل')}</p>` : `<p>${esc(item.content)}</p>`;
      return `<article class="concept-card concept-${color}" data-board-item="${esc(item.id)}" style="left:${Number(item.x)||0}px;top:${Number(item.y)||0}px;width:${Number(item.width)||260}px"><header class="concept-card-head" data-board-drag="${esc(item.id)}"><span><i data-lucide="${item.type==='link'?'link':item.type==='task'?'list-checks':item.type==='text'?'align-left':'sticky-note'}"></i> ${esc(item.creatorName||'عضو تیم')}</span><button type="button" class="icon-button subtle" data-edit-board-item="${esc(item.id)}" title="ویرایش کارت"><i data-lucide="pencil"></i></button></header><div class="concept-card-content" data-edit-board-item="${esc(item.id)}"><strong>${esc(item.title||'بدون عنوان')}</strong>${body}</div><footer><span>${fmtTime(item.updatedAt)}</span><span>برای جابه‌جایی، سربرگ را بکشید</span></footer></article>`;
    }).join('');
    return `${heading('برد ایده‌های مشترک','یک بوم آزاد برای چیدن ایده‌ها، پیوندها، متن‌ها و کارهای تیمی.',`<button class="secondary-button" data-action="new-board"><i data-lucide="plus"></i> برد تازه</button><button class="primary-button" data-action="new-board-item"><i data-lucide="sticky-note"></i> افزودن کارت</button>`)}
      <section class="panel shared-board-toolbar"><div class="toolbar"><div class="toolbar-right"><label class="field compact-field"><span>برد فعال</span><select id="sharedBoardSelect">${state.boards.map(b=>`<option value="${esc(b.id)}" ${b.id===state.activeBoardId?'selected':''}>${esc(b.title)}${b.locked?' · قفل':''}</option>`).join('')}</select></label><span class="live-presence"><i></i> همگام‌سازی زنده · اتصال WebSocket</span></div><small>${active?esc(active.description):'برد مشترک فضای کاری'}</small></div></section>
      <div class="concept-canvas-wrap"><div class="concept-canvas" id="conceptCanvas">${cards || `<div class="canvas-empty">${empty('layout-grid','بوم هنوز خالی است','اولین یادداشت یا ایده را روی بوم قرار دهید.')}</div>`}</div></div>`;
  }
  function driveEntry(item) {
    const icon = item.type==='folder'?'folder':item.type==='text'?'file-text':'file';
    return `<article class="drive-item ${item.locked?'is-locked':''}"><button class="drive-open" data-open-drive-node="${esc(item.id)}"><span class="drive-icon ${item.type}"><i data-lucide="${icon}"></i></span><span class="drive-copy"><strong>${esc(item.title)}</strong><small>${item.type==='folder'?'پوشه':item.type==='text'?'یادداشت Markdown':formatBytes(item.sizeBytes||0)} · ${item.accessMode==='team'?'اشتراک تیمی':item.accessMode==='password'?'محافظت‌شده':'اشتراک فضای کار'}</small></span>${item.locked?'<i data-lucide="lock" class="drive-lock"></i>':'<i data-lucide="chevron-left" class="drive-arrow"></i>'}</button><div class="drive-actions"><button class="icon-button subtle" data-copy-node="${esc(item.id)}" title="کپی پیوند"><i data-lucide="link"></i></button>${item.type==='file'?`<button class="icon-button subtle" data-download-node="${esc(item.id)}" title="دریافت"><i data-lucide="download"></i></button>`:''}${(isAdmin()||item.createdBy===state.me.id)?`<button class="icon-button subtle" data-share-node="${esc(item.id)}" title="تنظیمات اشتراک"><i data-lucide="shield"></i></button><button class="icon-button subtle" data-delete-node="${esc(item.id)}" title="حذف"><i data-lucide="trash-2"></i></button>`:''}</div></article>`;
  }
  function renderSharedDrive() {
    const crumbs = state.driveTrail.map((x,i)=>`<button class="text-button" data-drive-crumb="${i}">${esc(x.title)}</button>`).join('<i data-lucide="chevron-left"></i>');
    return `${heading('فایل‌ها و پوشه‌های مشترک','فضای مشترک تیم برای فایل‌ها، پوشه‌ها و محتوای متنی؛ با دسترسی عمومی، تیمی یا گذرواژه.',`<button class="secondary-button" data-action="new-folder"><i data-lucide="folder-plus"></i> پوشه جدید</button><button class="secondary-button" data-action="new-note"><i data-lucide="notebook-pen"></i> یادداشت جدید</button><button class="primary-button" data-action="upload-shared"><i data-lucide="upload"></i> بارگذاری فایل</button>`)}
      <section class="panel drive-panel"><div class="drive-toolbar"><div class="drive-breadcrumb"><button class="text-button" data-drive-root>فضای مشترک</button>${crumbs}</div><span class="quiet-tag">تا ۵۰ مگابایت برای هر فایل</span></div>
      <div id="driveUploadProgress" class="upload-progress-wrap hidden"><div class="upload-progress-copy"><strong id="driveUploadName">در حال بارگذاری فایل</strong><span id="driveUploadPercent">۰٪</span></div><div class="progress-track"><span id="driveUploadBar"></span></div></div>
      <input id="driveUploadInput" type="file" class="visually-hidden" />
      <div class="drive-list">${state.driveItems.map(driveEntry).join('') || empty('folder-open','این پوشه خالی است','یک پوشه، یادداشت یا فایل به فضای مشترک اضافه کنید.')}</div></section>`;
  }
  function renderSharedNotes() {
    const notes = [];
    const walk = items => items.forEach(x=>{ if(x.type==='text') notes.push(x); });
    walk(state.driveItems);
    return `${heading('یادداشت‌های Markdown','یادداشت‌های مشترک با پشتیبانی Markdown و پیش‌نمایش امن.',`<button class="primary-button" data-action="new-note"><i data-lucide="plus"></i> یادداشت تازه</button><button class="secondary-button" data-page-link="shared-drive">بازکردن فضای فایل‌ها</button>`)}<section class="panel notes-index"><p class="form-hint">یادداشت‌ها در ریشه فضای مشترک نمایش داده می‌شوند. برای یادداشت‌های داخل پوشه، از فضای فایل‌ها وارد همان پوشه شوید.</p>${notes.map(n=>`<button class="note-index-row" data-open-drive-node="${esc(n.id)}"><i data-lucide="file-text"></i><span><strong>${esc(n.title)}</strong><small>${fmtTime(n.updatedAt)} · ${n.accessMode==='password'?'گذرواژه‌دار':n.accessMode==='team'?'تیمی':'مشترک'}</small></span><i data-lucide="chevron-left"></i></button>`).join('')||empty('notebook-pen','یادداشتی ثبت نشده','یک یادداشت تازه بسازید؛ می‌توانید از Markdown کامل استفاده کنید.')}</section>`;
  }
  function renderTeamChat() {
    const channelName = state.chatChannel==='workspace'?'گفت‌وگوی عمومی':(state.teams.find(t=>t.id===state.chatTeamId)?.name||'گفت‌وگوی تیم');
    return `${heading('گفت‌وگوی تیمی','هماهنگی‌های روزمره را در یک گفت‌وگوی سبک کنار کارها نگه دارید.',`<span class="live-presence"><i></i> همگام‌سازی زنده</span>`)}
      <section class="panel chat-panel"><div class="chat-head"><div><h2>${esc(channelName)}</h2><small>پیام‌های این کانال برای اعضای مجاز فضای کاری قابل مشاهده است.</small></div><label class="field compact-field"><span>کانال</span><select id="chatChannelSelect"><option value="workspace" ${state.chatChannel==='workspace'?'selected':''}>عمومی فضای کاری</option>${state.teams.filter(t=>(t.memberIds||[]).includes(state.me.id)||isAdmin()).map(t=>`<option value="${esc(t.id)}" ${state.chatChannel==='team'&&state.chatTeamId===t.id?'selected':''}>تیم ${esc(t.name)}</option>`).join('')}</select></label></div>
      <div class="chat-presence" id="chatPresence">${state.chatPresence.map(p=>`<span class="presence-chip">${esc(p.name)} <small>${esc(p.page)}</small></span>`).join('')}</div>
      <div class="chat-messages" id="chatMessages">${state.chatMessages.map(m=>`<article class="chat-message ${m.userId===state.me.id?'mine':''}"><span class="chat-avatar">${esc(initials(m.userName).slice(0,1))}</span><div class="chat-message-body"><header><strong>${esc(m.userName)}</strong><small>${fmtTime(m.createdAt)}</small></header><p>${esc(m.body).replace(/\n/g,'<br>')}</p></div></article>`).join('')||empty('messages-square','گفت‌وگو هنوز شروع نشده','اولین پیام را برای هم‌تیمی‌ها بفرستید.')}</div>
      <form id="chatComposeForm" class="chat-compose"><textarea name="body" rows="2" maxlength="5000" placeholder="پیامتان را بنویسید..." required></textarea><button class="primary-button"><i data-lucide="send"></i> ارسال پیام</button></form></section>`;
  }
  async function loadDrive(parentId = state.driveParentId, password = '') {
    const q = new URLSearchParams(); if(parentId) q.set('parent_id',parentId); if(password) q.set('password',password);
    try {
      const data=await api(`/api/drive${q.size?'?'+q.toString():''}`); state.driveItems=data.items||[]; state.driveParentId=parentId; state.drivePassword=password;
      if(parentId && state.driveTrail.at(-1)?.id!==parentId){ const node=await api(`/api/drive/nodes/${parentId}?password=${encodeURIComponent(password)}`); state.driveTrail.push({id:node.id,title:node.title}); }
      if(!parentId) state.driveTrail=[];
      render();
    } catch(e) {
      if(e.message.includes('گذرواژه')) { const pass=prompt('این پوشه با گذرواژه محافظت شده است:'); if(pass) return loadDrive(parentId,pass); }
      toast(e.message,'lock');
    }
  }
  async function loadChat() {
    const params=new URLSearchParams({channel_type:state.chatChannel}); if(state.chatChannel==='team'&&state.chatTeamId) params.set('team_id',state.chatTeamId);
    const draft=$('chatComposeForm')?.elements.body?.value||''; const data=await api(`/api/chat?${params.toString()}`); state.chatMessages=data.items||[];
    const presence=await api('/api/presence').catch(()=>({items:[]})); state.chatPresence=presence.items||[];
    render();
    const form=$('chatComposeForm'); if(form&&draft)form.elements.body.value=draft; const box=$('chatMessages'); if(box) box.scrollTop=box.scrollHeight;
  }
  function renderMarkdown(source) {
    try {
      if(window.marked?.parse) {
        const html=window.marked.parse(source||'',{gfm:true,breaks:false});
        return window.DOMPurify?.sanitize ? window.DOMPurify.sanitize(html,{USE_PROFILES:{html:true}}) : esc(source).replace(/\n/g,'<br>');
      }
    } catch(_) {}
    return esc(source).replace(/\n/g,'<br>');
  }
  function updateMarkdownPreview() { const preview=$('mdPreview'); const input=$('mdSource'); if(preview&&input) preview.innerHTML=renderMarkdown(input.value); }
  function openMarkdownEditor(node = null, parentId = state.driveParentId) {
    const body=`<form id="sharedNoteForm" class="form-stack" data-node-id="${esc(node?.id||'')}" data-parent-id="${esc(parentId||'')}">
      <label class="field"><span>عنوان یادداشت</span><input name="title" required maxlength="180" value="${esc(node?.title||'')}" placeholder="مثلاً ایده‌های جلسه برنامه‌ریزی" /></label>
      <div class="md-editor-tabs"><button type="button" class="md-tab active" data-md-tab="write">نوشتن Markdown</button><button type="button" class="md-tab" data-md-tab="preview">پیش‌نمایش</button><span>Markdown · GFM</span></div>
      <textarea id="mdSource" name="content" class="md-source" rows="16" maxlength="100000" placeholder="# عنوان\n\nمتن یادداشت، **تأکید**، فهرست، جدول و کد...">${esc(node?.content||'')}</textarea><div id="mdPreview" class="markdown-preview hidden"></div>
      ${node?'<p class="form-hint">تنظیمات اشتراک از دکمه سپر کنار یادداشت در فضای فایل‌ها قابل تغییر است.</p>':`<div class="form-grid">${shareControls('noteShare')}</div>`}
      <div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ذخیره یادداشت</button></div></form>`;
    showModal(node?'ویرایش یادداشت':'یادداشت Markdown تازه',body,'یادداشت مشترک'); updateMarkdownPreview();
  }
  function openDriveNodeCreator(type='folder') {
    const isFolder=type==='folder';
    const body=`<form id="driveNodeForm" class="form-stack"><input type="hidden" name="node_type" value="${type}"/><label class="field"><span>${isFolder?'نام پوشه':'عنوان یادداشت'}</span><input name="title" required maxlength="180" /></label>${isFolder?'':`<label class="field"><span>متن Markdown</span><textarea name="content" rows="8" maxlength="100000" placeholder="# یادداشت تیم\n\nمتن را با Markdown بنویسید..." required></textarea></label>`}<div class="form-grid">${shareControls('nodeShare')}</div><p class="form-hint">${isFolder?'دسترسی پوشه به محتویات داخل آن نیز اعمال می‌شود.':'برای ویرایش و پیش‌نمایش کامل، بعد از ساخت یادداشت آن را باز کنید.'}</p><div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">${isFolder?'ساخت پوشه':'ساخت یادداشت'}</button></div></form>`;
    showModal(isFolder?'پوشه جدید':'یادداشت جدید',body,'فضای مشترک');
  }
  async function openDriveNode(nodeId) {
    const node=state.driveItems.find(x=>x.id===nodeId);
    let password=state.drivePassword||'';
    if(node?.locked) password='';
    let detail;
    try {
      const q=password?`?password=${encodeURIComponent(password)}`:'';
      detail=await api(`/api/drive/nodes/${nodeId}${q}`);
    } catch(e) {
      if(!e.message.includes('گذرواژه')) { toast(e.message,'alert-circle'); return; }
      password=prompt('این مورد یا پوشه والد با گذرواژه محافظت شده است:')||'';
      if(!password)return;
      try { detail=await api(`/api/drive/nodes/${nodeId}?password=${encodeURIComponent(password)}`); }
      catch(err){toast(err.message,'lock');return;}
    }
    if(detail.type==='folder') { await loadDrive(detail.id,password); return; }
    if(detail.type==='text') { state.drivePassword=password; openMarkdownEditor(detail,state.driveParentId); $('mdSource').value=detail.content||''; updateMarkdownPreview(); return; }
    if(detail.type==='file') { window.location.href=`/api/drive/nodes/${nodeId}/download${password?'?password='+encodeURIComponent(password):''}`; }
  }
  async function openShareSettings(node) {
    let acl=[]; if(isOwner()) acl=(await api(`/api/drive/nodes/${node.id}/role-permissions`).catch(()=>({items:[]}))).items||[];
    const aclHtml=isOwner()?`<section class="acl-editor"><strong>دسترسی نقش‌ها در این مورد و زیرپوشه‌ها</strong>${['admin','member'].map(role=>{const item=acl.find(x=>x.role===role);return `<div class="acl-role"><strong>${roleLabel(role)}</strong><label><input type="checkbox" name="acl-read-${role}" ${item?item.can_read?'checked':'':'checked'}/> مشاهده</label><label><input type="checkbox" name="acl-write-${role}" ${item?item.can_write?'checked':'':'checked'}/> ویرایش</label></div>`;}).join('')}<small>مالک همیشه دسترسی کامل دارد. تنظیم این مجوزها روی تمام محتویات پوشه نیز اعمال می‌شود.</small></section>`:'';
    const body=`<form id="shareSettingsForm" class="form-stack" data-node-id="${esc(node.id)}"><label class="field"><span>نحوه دسترسی</span><select name="access_mode" id="shareEditAccess"><option value="workspace" ${node.accessMode==='workspace'?'selected':''}>همه اعضای فضای کاری</option><option value="team" ${node.accessMode==='team'?'selected':''}>فقط یک تیم مشخص</option><option value="password" ${node.accessMode==='password'?'selected':''}>محافظت با گذرواژه</option></select></label><label class="field ${node.accessMode==='team'?'':'hidden'}" id="shareEditTeamWrap"><span>تیم مجاز</span><select name="team_id">${teamOptions(node.teamId)}</select></label><label class="field ${node.accessMode==='password'?'':'hidden'}" id="shareEditPasswordWrap"><span>گذرواژه جدید (برای حفظ گذرواژه فعلی خالی بگذارید)</span><input type="password" name="password" minlength="8" /></label>${aclHtml}<p class="form-hint">پیوند اشتراک داخل شبکه به حساب BottleNeck و دسترسی مجاز نیاز دارد؛ فایل‌ها عمومی اینترنتی نمی‌شوند.</p><div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ذخیره دسترسی</button></div></form>`;
    showModal('تنظیمات اشتراک',body,'دسترسی فایل و پوشه');
  }
  function uploadSharedFile(file) {
    if(file.size>50*1024*1024){toast('حداکثر حجم فایل ۵۰ مگابایت است.','alert-circle');return;}
    const wrap=$('driveUploadProgress'); if(!wrap)return; wrap.classList.remove('hidden'); $('driveUploadName').textContent=file.name; $('driveUploadPercent').textContent='۰٪'; $('driveUploadBar').style.width='0%';
    const xhr=new XMLHttpRequest(); const settings=state.uploadShareSettings||{access_mode:'workspace'}; const query=new URLSearchParams({access_mode:settings.access_mode||'workspace'}); if(state.driveParentId)query.set('parent_id',state.driveParentId); if(settings.team_id)query.set('team_id',settings.team_id);
    xhr.open('POST',`/api/drive/upload?${query.toString()}`); xhr.withCredentials=true;
    xhr.setRequestHeader('Content-Type',file.type||'application/octet-stream'); xhr.setRequestHeader('X-File-Name',encodeURIComponent(file.name)); if(state.drivePassword)xhr.setRequestHeader('X-Folder-Password',state.drivePassword); if(settings.password)xhr.setRequestHeader('X-Share-Password',settings.password);
    xhr.upload.onprogress=e=>{if(e.lengthComputable){const percent=Math.round(e.loaded/e.total*100);$('driveUploadPercent').textContent=faNum(percent)+'٪';$('driveUploadBar').style.width=percent+'%';}};
    xhr.onload=async()=>{let data={};try{data=JSON.parse(xhr.responseText);}catch(_){}if(xhr.status>=200&&xhr.status<300){state.uploadShareSettings=null;$('driveUploadPercent').textContent='۱۰۰٪';$('driveUploadBar').style.width='100%';toast('فایل با موفقیت به فضای مشترک اضافه شد.','upload');await loadDrive();}else toast(data.detail||'بارگذاری فایل انجام نشد.','alert-circle');};
    xhr.onerror=()=>toast('ارتباط هنگام بارگذاری قطع شد.','alert-circle'); xhr.send(file);
  }
  function reloadLivePage() {
    if(state.page==='shared-board' && !boardPointer) loadBoardItems().catch(()=>{});
    else if(state.page==='shared-drive'||state.page==='shared-notes') loadDrive(state.driveParentId,state.drivePassword).catch(()=>{});
    else if(state.page==='team-chat') loadChat().catch(()=>{});
  }

  function renderOverview() {
    const tasks = state.tasks; const total = tasks.length;
    const done = tasks.filter(t => t.status === 'done').length;
    const progress = tasks.filter(t => t.status === 'in-progress').length;
    const dueSoon = tasks.filter(t => t.status !== 'done' && t.dueDate && t.dueDate >= todayISO()).length;
    const late = tasks.filter(overdue).length; const percent = total ? Math.round(done / total * 100) : 0;
    const upcoming = tasks.filter(t => t.status !== 'done').slice(0, 6);
    const maxLoad = Math.max(1, ...state.users.map(u => u.open_tasks || 0));
    const loads = state.users.map(u => `<div class="team-load-row">${avatar(u,'avatar-xs')}<div class="team-load-meta"><strong>${esc(u.name)}</strong><small>${roleLabel(u.role)}</small></div><div class="load-track"><span style="width:${Math.round((u.open_tasks || 0)/maxLoad*100)}%"></span></div><b class="load-number">${faNum(u.open_tasks || 0)}</b></div>`).join('');
    return `${heading(`سلام ${state.me.name.split(' ')[0]}، آماده‌ای؟`, 'نمایی روشن از کارهای باز، موعدها و اتفاق‌های تازه.', `<button class="secondary-button" data-page-link="handbook"><i data-lucide="book-open"></i> راهنمای شروع</button><button class="primary-button" data-action="new-task"><i data-lucide="plus"></i> ثبت کار جدید</button>`)}
      <div class="overview-grid"><div class="main-column"><div class="stat-grid">
        <article class="stat-card"><div class="stat-top"><span>همه کارها</span><i data-lucide="layers"></i></div><strong class="stat-number">${faNum(total)}</strong><div class="stat-foot"><span class="stat-caption">ثبت‌شده در فضای کار</span></div></article>
        <article class="stat-card"><div class="stat-top"><span>در حال انجام</span><i data-lucide="activity"></i></div><strong class="stat-number">${faNum(progress)}</strong><div class="stat-foot"><span class="stat-caption">فعال و در جریان</span></div></article>
        <article class="stat-card"><div class="stat-top"><span>تکمیل‌شده</span><i data-lucide="check-circle-2"></i></div><strong class="stat-number">${faNum(done)}</strong><div class="stat-foot"><span class="stat-caption">${faNum(percent)}٪ از کل کارها</span></div></article>
        <article class="stat-card stat-card-alert"><div class="stat-top"><span>از موعد گذشته</span><i data-lucide="calendar-clock"></i></div><strong class="stat-number">${faNum(late)}</strong><div class="stat-foot"><span class="stat-caption">${faNum(dueSoon)} کار موعددار باز</span></div></article>
      </div>
      <section class="panel"><div class="panel-heading"><h2>کارهای پیش رو</h2><button class="text-button" data-page-link="all-tasks">دیدن همه کارها ←</button></div>
        ${upcoming.length ? `<div class="task-list">${upcoming.map(taskRow).join('')}</div>` : empty('inbox','هنوز کاری ثبت نشده','اولین کار مشترک را ایجاد کنید تا برنامه شکل بگیرد.')}
      </section>
      <section class="panel" style="margin-top:14px"><div class="panel-heading"><h2>آخرین اتفاق‌ها</h2><button class="text-button" data-page-link="activity">گزارش کامل ←</button></div>${activityItems(state.activity.slice(0,5))}</section>
      </div><aside class="right-column"><section class="progress-panel"><div class="panel-heading"><h2>پیشرفت کلی</h2><i data-lucide="chart-no-axes-combined" class="panel-icon"></i></div><div class="ring-wrap"><div class="progress-ring" style="--progress:${percent}%"><div class="ring-inner"><strong>${faNum(percent)}٪</strong><span>تکمیل کارها</span></div></div></div><div class="progress-legend"><div><span class="legend-dot done"></span>تکمیل‌شده <b>${faNum(done)}</b></div><div><span class="legend-dot doing"></span>در حال انجام <b>${faNum(progress)}</b></div><div><span class="legend-dot todo"></span>سایر وضعیت‌ها <b>${faNum(total-done-progress)}</b></div></div><p class="panel-footnote">درصد بر پایه تعداد کارهای تکمیل‌شده از مجموع کارها محاسبه می‌شود.</p></section>
      <section class="panel team-load-panel"><div class="panel-heading"><h2>بار کاری اعضا</h2><small>${faNum(state.users.length)} عضو</small></div>${loads || empty('users','هنوز عضوی نیست','اعضای تیم را دعوت کنید.')}</section>
      <div class="quick-tip"><span class="tip-mark">/</span><div><strong>میان‌بُر روزانه</strong><p>برای ثبت سریع کار جدید کلید N و برای جست‌وجو Ctrl + K را بزنید.</p></div></div></aside></div>`;
  }
  function taskRow(task) {
    const people = task.assignees?.length ? avatarStack(task.assignees) : avatarStack([]);
    return `<div class="task-row" data-open-task="${esc(task.id)}"><span class="task-check ${task.status === 'done' ? 'checked' : ''}" aria-hidden="true">${task.status === 'done' ? '<i data-lucide="check"></i>' : ''}</span><div class="task-main-text"><strong>${esc(task.title)}</strong><small>${esc(task.projectName || projectOf(task.projectId).name)} · ${esc(task.teamName || teamOf(task.teamId).name)}</small></div><div class="task-person">${people}<span>${esc(task.assignees?.map(a=>a.name).join('، ') || 'بدون مسئول')}</span></div><div>${priorityPill(task.priority)}</div><div>${statusPill(task.status)}</div><span class="task-due ${overdue(task) ? 'late' : ''}">${fmtDate(task.dueDate)}</span></div>`;
  }
  function renderTasks(onlyMine) {
    let tasks = tasksFiltered(onlyMine);
    if (state.taskFilter !== 'all') tasks = tasks.filter(t => state.taskFilter === 'open' ? t.status !== 'done' : t.status === 'done');
    const title = onlyMine ? 'کارهای من' : 'همه کارها';
    return `${heading(title, onlyMine ? 'کارهایی که شما یکی از مسئولان آن هستید.' : 'فهرست کارهای مشترک فضای کاری و وضعیت هرکدام.', `<button class="primary-button" data-action="new-task"><i data-lucide="plus"></i> کار جدید</button>`)}
      <section class="panel table-panel"><div class="toolbar"><div class="filter-tabs"><button class="filter-tab ${state.taskFilter==='all'?'active':''}" data-task-filter="all">همه (${faNum(tasksFiltered(onlyMine).length)})</button><button class="filter-tab ${state.taskFilter==='open'?'active':''}" data-task-filter="open">باز</button><button class="filter-tab ${state.taskFilter==='done'?'active':''}" data-task-filter="done">تکمیل‌شده</button></div><div class="toolbar-right"><select class="select-control" id="statusFilter"><option value="">همه وضعیت‌ها</option>${STATUSES.map(s=>`<option value="${s.id}">${esc(statusOf(s.id).label)}</option>`).join('')}</select><select class="select-control" id="teamFilter"><option value="">همه تیم‌ها</option>${state.teams.map(t=>`<option value="${esc(t.id)}">${esc(t.name)}</option>`).join('')}</select></div></div>
      <div class="task-table-wrap"><table class="task-table"><thead><tr><th>عنوان کار</th><th>مسئولان</th><th>اولویت</th><th>وضعیت</th><th>موعد</th><th>پیوست / چک‌لیست</th></tr></thead><tbody id="taskRows">${tasks.map(t=>`<tr data-open-task="${esc(t.id)}"><td><span class="table-task-name"><span class="task-check ${t.status==='done'?'checked':''}">${t.status==='done'?'<i data-lucide="check"></i>':''}</span><span>${esc(t.title)}<small style="display:block;color:#9da197;font-size:8px;margin-top:4px">${esc(t.projectName || projectOf(t.projectId).name)}</small></span></span></td><td><span class="person-cell">${avatarStack(t.assignees||[])} <small>${faNum(t.assignees?.length||0)}</small></span></td><td>${priorityPill(t.priority)}</td><td>${statusPill(t.status)}</td><td><span class="task-due ${overdue(t)?'late':''}">${fmtDate(t.dueDate)}</span></td><td><small>${faNum(t.attachmentCount||0)} فایل · ${faNum(t.checklistDone||0)}/${faNum(t.checklist||0)}</small></td></tr>`).join('') || `<tr><td colspan="6">${empty('list-checks','کاری پیدا نشد','فیلترها را تغییر دهید یا یک کار تازه بسازید.')}</td></tr>`}</tbody></table></div></section>`;
  }
  function renderBoard() {
    const tasks = tasksFiltered(false);
    return `${heading('برد کانبان','جریان کار را با جابه‌جایی کارت‌ها مدیریت کنید.', `<button class="primary-button" data-action="new-task"><i data-lucide="plus"></i> کار جدید</button>`)}<div class="kanban-board" id="kanbanBoard">${STATUSES.map(col => {
      const list = tasks.filter(t=>t.status===col.id);
      return `<section class="kanban-column" data-drop-status="${col.id}"><div class="kanban-head"><strong>${esc(statusOf(col.id).label)}</strong><span>${faNum(list.length)}</span></div><div class="kanban-cards">${list.map(t=>`<article class="kanban-card" draggable="true" data-drag-task="${esc(t.id)}"><div class="data-card-top">${priorityPill(t.priority)}<button class="icon-button subtle" data-open-task="${esc(t.id)}" aria-label="جزئیات"><i data-lucide="arrow-up-left"></i></button></div><h3 data-open-task="${esc(t.id)}">${esc(t.title)}</h3><small>${esc(t.projectName || projectOf(t.projectId).name)}</small><div class="kanban-card-foot" style="margin-top:12px"><span>${fmtDate(t.dueDate)}</span>${avatarStack(t.assignees||[])}</div>${t.checklist ? `<div class="inline-progress"><span style="width:${Math.round((t.checklistDone||0)/t.checklist*100)}%"></span></div>` : ''}</article>`).join('') || `<div class="empty-state">کار دیگری نیست</div>`}</div></section>`;
    }).join('')}</div>`;
  }
  function renderCalendar() {
    const y = state.month.getFullYear(), m = state.month.getMonth();
    const start = new Date(y,m,1); const offset = (start.getDay()+1)%7; // Saturday-first week
    const days = new Date(y,m+1,0).getDate(); const cells = Math.ceil((offset+days)/7)*7;
    const monthName = new Date(y,m,1).toLocaleDateString('fa-IR',{year:'numeric',month:'long'});
    const weekdays = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه'];
    let grid = weekdays.map(d=>`<div class="calendar-cell calendar-weekday">${d}</div>`).join('');
    for (let i=0;i<cells;i++) {
      const day = i-offset+1; const valid = day>=1&&day<=days; const date = new Date(y,m,valid?day:day<1?day:day-days);
      const iso = `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
      const events = state.tasks.filter(t=>t.dueDate===iso).slice(0,3);
      grid += `<div class="calendar-cell ${valid?'':'muted'} ${iso===todayISO()?'today':''}"><span class="calendar-day-number">${faNum(date.getDate())}</span>${events.map(t=>`<button class="calendar-event ${t.status==='done'?'green':t.priority==='urgent'?'':''}" data-open-task="${esc(t.id)}">${esc(t.title)}</button>`).join('')}</div>`;
    }
    return `${heading('تقویم','موعدهای ثبت‌شده در کارها را در نمای ماهانه ببینید.') }<section class="panel calendar-panel"><div class="calendar-month-head"><button class="icon-button" data-calendar="prev"><i data-lucide="chevron-right"></i></button><strong>${monthName}</strong><button class="icon-button" data-calendar="next"><i data-lucide="chevron-left"></i></button></div><div class="calendar-grid">${grid}</div></section>`;
  }
  function renderProjects() {
    const cards = state.projects.map(p=>{
      const linked = state.tasks.filter(t=>t.projectId===p.id); const done = linked.filter(t=>t.status==='done').length; const percent = linked.length ? Math.round(done/linked.length*100) : 0;
      return `<article class="data-card"><div class="data-card-top"><span class="project-mark"><i data-lucide="folder-kanban"></i></span><span class="quiet-tag">${p.status==='active'?'فعال':p.status==='completed'?'تکمیل‌شده':'بایگانی'}</span></div><h3>${esc(p.name)}</h3><p>${esc(p.description || 'بدون توضیحات')}</p><div class="project-progress"><div class="project-progress-label"><span>${faNum(done)} از ${faNum(linked.length)} کار تکمیل شده</span><b>${faNum(percent)}٪</b></div><div class="project-progress-track"><span style="width:${percent}%"></span></div></div><div class="data-card-actions"><button class="secondary-button" data-project-tasks="${esc(p.id)}">دیدن کارها</button><button class="icon-button" data-edit-project="${esc(p.id)}" title="ویرایش"><i data-lucide="pencil"></i></button>${isAdmin()?`<button class="icon-button" data-delete-project="${esc(p.id)}" title="حذف"><i data-lucide="trash-2"></i></button>`:''}</div></article>`;
    }).join('');
    return `${heading('پروژه‌ها','کارهای مرتبط با یک نتیجه یا ابتکار را کنار هم نگه دارید.', `<button class="primary-button" data-action="new-project"><i data-lucide="plus"></i> پروژه جدید</button>`)}<div class="data-grid">${cards || empty('folder-kanban','پروژه‌ای ساخته نشده','برای یک هدف مشترک، اولین پروژه را ایجاد کنید.')}</div>`;
  }
  function renderTeams() {
    const teamCards = state.teams.map(t=>`<article class="data-card"><div class="data-card-top"><span class="project-mark"><i data-lucide="users-round"></i></span><span class="quiet-tag">${faNum(t.members?.length||0)} عضو</span></div><h3>${esc(t.name)}</h3><p>${esc(t.description||'بدون توضیحات')}</p><div class="avatar-stack" style="margin-top:15px">${(t.members||[]).slice(0,6).map(u=>avatar(u,'avatar-xs')).join('')}</div><div class="data-card-actions">${isAdmin()?`<button class="secondary-button" data-manage-team="${esc(t.id)}">مدیریت اعضا</button><button class="icon-button" data-delete-team="${esc(t.id)}" title="حذف تیم"><i data-lucide="trash-2"></i></button>`:''}</div></article>`).join('');
    const members = state.users.map(u=>`<div class="team-member-row">${avatar(u)}<div class="member-info"><strong>${esc(u.name)}</strong><small>${esc(u.email)}</small></div>${rolePill(u.role)}<span class="quiet-tag">${faNum(u.open_tasks||0)} کار باز</span></div>`).join('');
    const invites = state.invitations.map(i=>`<div class="invite-row"><strong>${esc(i.email)}</strong><small>${roleLabel(i.role)} · انقضا ${fmtDate(i.expires_at?.slice(0,10))}</small><button class="icon-button" data-revoke-invite="${esc(i.id)}" title="لغو دعوت"><i data-lucide="x"></i></button></div>`).join('');
    const actions = `${isAdmin()?'<button class="secondary-button" data-action="new-team"><i data-lucide="users"></i> ساخت تیم</button><button class="primary-button" data-action="invite"><i data-lucide="user-plus"></i> دعوت عضو</button>':''}`;
    return `${heading('تیم‌ها و اعضا','اعضا را به گروه‌های کاری اضافه کنید و دعوت‌نامه‌های فعال را مدیریت کنید.',actions)}<div class="section-heading"><h2>تیم‌ها</h2><span class="quiet-tag">عضویت در تیم‌ها مستقل از مسئولیت هر کار است.</span></div><div class="data-grid">${teamCards || empty('users','تیمی وجود ندارد','یک تیم تازه بسازید.')}</div><div class="overview-grid" style="margin-top:20px"><section class="panel"><div class="panel-heading"><h2>اعضای فضای کار</h2><small>${faNum(state.users.length)} نفر</small></div>${members}</section><section class="panel"><div class="panel-heading"><h2>دعوت‌های در انتظار</h2><small>${faNum(state.invitations.length)} دعوت</small></div>${invites || empty('mail-check','دعوت فعالی نیست','لینک دعوت را برای همکار بعدی بسازید.')}</section></div>`;
  }
  function activityItems(items) {
    if (!items.length) return empty('activity','هنوز فعالیتی ثبت نشده','پس از شروع کارها، رویدادها در اینجا دیده می‌شوند.');
    return `<div class="activity-list">${items.map(a=>`<div class="activity-item"><span class="activity-symbol"><i data-lucide="${a.action==='created'?'plus-circle':a.action==='commented'?'message-circle':a.action==='status_changed'?'refresh-cw':a.action==='uploaded'?'paperclip':'activity'}"></i></span><div class="activity-copy"><strong>${esc(a.user_name||'عضو فضای کار')}</strong> ${esc(a.message)}<small>${fmtTime(a.created_at)}</small></div></div>`).join('')}</div>`;
  }
  function renderActivity() { return `${heading('گزارش فعالیت','ردپای تغییرات و گفت‌وگوهای مهم فضای کاری.') }<section class="panel activity-full-panel">${activityItems(state.activity)}</section>`; }
  function formatDuration(seconds) {
    const total=Math.max(0,Number(seconds||0)); const h=Math.floor(total/3600); const m=Math.floor((total%3600)/60); const sec=total%60;
    return h ? `${faNum(h)}:${String(m).padStart(2,'0')}` : `${faNum(m)} دقیقه${sec>=0&&m===0?` و ${faNum(sec)} ثانیه`:''}`;
  }
  function renderRecurring() {
    const cards=(state.recurringRules||[]).map(r=>`<article class="data-card"><div class="data-card-top"><span class="project-mark"><i data-lucide="repeat"></i></span><span class="quiet-tag">${r.is_active?'فعال':'متوقف'}</span></div><h3>${esc(r.title)}</h3><p>${esc(r.description||'بدون توضیحات')}</p><div class="recurring-meta"><span>${({daily:'روزانه',weekly:'هفتگی',monthly:'ماهانه'})[r.cadence]} · هر ${faNum(r.interval_count)} دوره</span><strong>بعدی: ${fmtDate(r.next_run_on)}</strong></div><div class="data-card-actions">${isAdmin()?`<button class="secondary-button" data-toggle-recurring="${esc(r.id)}">${r.is_active?'توقف':'فعال‌سازی'}</button><button class="icon-button" data-delete-recurring="${esc(r.id)}"><i data-lucide="trash-2"></i></button>`:''}</div></article>`).join('');
    return `${heading('کارهای تکرارشونده','برای کارهایی که طبق برنامه دوباره انجام می‌شوند، قانون بسازید.',isAdmin()?'<button class="primary-button" data-action="new-recurring"><i data-lucide="plus"></i> قانون جدید</button>':'')}<div class="data-grid">${cards||empty('repeat','قانون تکراری ندارید','یک کار روزانه، هفتگی یا ماهانه تعریف کنید.')}</div><p class="form-hint recurring-footnote">کارهای سررسیدشده هنگام بازشدن فضای کار ساخته می‌شوند. رایانه میزبان و سرویس BottleNeck باید روشن باشند.</p>`;
  }
  function renderTemplates() {
    const cards=(state.templates||[]).map(t=>`<article class="data-card"><div class="data-card-top"><span class="project-mark"><i data-lucide="copy-check"></i></span><span class="quiet-tag">${faNum(t.checklist?.length||0)} قدم</span></div><h3>${esc(t.name)}</h3><p>${esc(t.description||t.title)}</p><div class="recurring-meta"><span>${esc(t.title)}</span><strong>${esc(priorityOf(t.priority).label)}</strong></div><div class="data-card-actions"><button class="primary-button" data-use-template="${esc(t.id)}"><i data-lucide="plus"></i> ساخت کار</button>${isAdmin()?`<button class="icon-button" data-delete-template="${esc(t.id)}"><i data-lucide="trash-2"></i></button>`:''}</div></article>`).join('');
    return `${heading('قالب‌های کار','کارهای پرتکرار را یک‌بار طراحی کنید و هر بار از همان ساختار استفاده کنید.',isAdmin()?'<button class="primary-button" data-action="new-template"><i data-lucide="plus"></i> قالب جدید</button>':'')}<div class="data-grid">${cards||empty('copy-check','قالبی ساخته نشده','برای یک فرایند تکراری، قالب استاندارد بسازید.')}</div>`;
  }
  function renderReports() {
    const d=state.reportData;
    return `${heading('گزارش‌های عملکرد','خروجی‌های ثبت‌شده و زمان واقعی صرف‌شده برای کارها.',`<div class="filter-tabs"><button class="filter-tab ${state.reportPeriod==='daily'?'active':''}" data-report-period="daily">روزانه</button><button class="filter-tab ${state.reportPeriod==='weekly'?'active':''}" data-report-period="weekly">هفتگی</button></div>`)}
      ${!d?`<section class="panel">${empty('chart-no-axes-combined','در حال آماده‌سازی گزارش','داده‌های بازه انتخاب‌شده دریافت می‌شوند.')}</section>`:`<div class="stat-grid report-stat-grid"><article class="stat-card"><div class="stat-top"><span>کارهای ایجادشده</span><i data-lucide="plus-circle"></i></div><strong class="stat-number">${faNum(d.summary.created)}</strong><div class="stat-foot"><span class="stat-caption">در بازه انتخاب‌شده</span></div></article><article class="stat-card"><div class="stat-top"><span>کارهای تکمیل‌شده</span><i data-lucide="check-circle"></i></div><strong class="stat-number">${faNum(d.summary.completed)}</strong><div class="stat-foot"><span class="stat-caption">در همین بازه</span></div></article><article class="stat-card"><div class="stat-top"><span>زمان ثبت‌شده</span><i data-lucide="timer"></i></div><strong class="stat-number">${formatDuration(d.trackedSeconds)}</strong><div class="stat-foot"><span class="stat-caption">مجموع زمان‌سنج‌ها</span></div></article><article class="stat-card stat-card-alert"><div class="stat-top"><span>کارهای عقب‌افتاده</span><i data-lucide="calendar-clock"></i></div><strong class="stat-number">${faNum(d.summary.overdue)}</strong><div class="stat-foot"><span class="stat-caption">از کل کارهای باز</span></div></article></div>
        <div class="overview-grid report-columns"><section class="panel"><div class="panel-heading"><h2>زمان ثبت‌شده بر اساس عضو</h2><small>${state.reportPeriod==='daily'?'امروز':'این هفته'}</small></div>${d.byUser.map(u=>`<div class="report-person"><span>${esc(u.name)}</span><div class="load-track"><span style="width:${Math.max(2,Math.round((u.seconds/Math.max(1,...d.byUser.map(x=>x.seconds)))*100))}%"></span></div><b>${formatDuration(u.seconds)}</b></div>`).join('')||empty('users','داده‌ای وجود ندارد','با شروع زمان‌سنج، گزارش اعضا ساخته می‌شود.')}</section><section class="panel"><div class="panel-heading"><h2>زمان بر اساس پروژه</h2><small>ساعت ثبت‌شده</small></div>${d.byProject.map(p=>`<div class="report-person"><span>${esc(p.name)}</span><div class="load-track"><span style="width:${Math.max(2,Math.round((p.seconds/Math.max(1,...d.byProject.map(x=>x.seconds)))*100))}%"></span></div><b>${formatDuration(p.seconds)}</b></div>`).join('')||empty('folder-kanban','زمانی ثبت نشده','زمان‌های ثبت‌شده روی کارهای پروژه اینجا دیده می‌شوند.')}</section></div>`}`;
  }
  function renderApprovals() {
    const items=state.pendingApprovals||[];
    return `${heading('درخواست‌های تأیید','خروجی‌هایی که برای بازبینی نهایی فرستاده شده‌اند.')}<section class="panel approvals-panel">${items.length?items.map(a=>`<div class="approval-row approval-page-row"><div><strong>${esc(a.task_title)}</strong><small>درخواست‌دهنده: ${esc(a.requester_name)} · ${fmtTime(a.requested_at)}</small></div><span class="quiet-tag">در انتظار بررسی</span><button class="secondary-button" data-open-task="${esc(a.task_id)}">مشاهده کار</button>${isAdmin()?`<button class="primary-button" data-approval="approved" data-approval-id="${esc(a.id)}">تأیید</button><button class="danger-button" data-approval="rejected" data-approval-id="${esc(a.id)}">رد</button>`:''}</div>`).join(''):empty('clipboard-check','درخواست بازی وجود ندارد','درخواست‌های جدید بازبینی در این صفحه نمایش داده می‌شوند.')}</section>`;
  }

  function renderHandbook() {
    return `${heading('راهنمای استفاده','راهنمای نسخه نهایی MVP، صفحه‌ها، دسترسی‌ها، امنیت و نگهداری داده‌ها.')}
      <article class="panel handbook">
        <p class="eyebrow">BottleNeck · نسخه ۰.۶.۰</p><h2>فضای کاری تیم را از یک نقطه مدیریت کنید</h2><p>BottleNeck ترکیبی از مدیریت کار، بهره‌وری، برد ایده‌ها، فایل‌ها و پوشه‌های مشترک، یادداشت‌های Markdown و گفت‌وگوی تیمی است. داده‌ها روی رایانه میزبان ذخیره می‌شوند و اعضای مجاز از مرورگر به همان سرور وصل می‌شوند.</p>
        <div class="handbook-callout">رایانه میزبان باید روشن و برنامه فعال باشد. آدرس محلی معمولاً <code>http://127.0.0.1:1939</code> و نشانی سایر دستگاه‌ها <code>http://IP-میزبان:1939</code> است.</div>
        <h2>۱. حساب، ورود و چند فضای کاری</h2><p>اولین حساب ثبت‌شده، مالک اولیه نصب است. هر کاربر می‌تواند عضو چند فضای کاری باشد و از انتخابگر بالای برنامه بین آنها جابه‌جا شود یا فضای تازه بسازد. دعوت‌نامه برای ایمیل مشخص ساخته می‌شود و ۷ روز اعتبار دارد. کاربر موجود می‌تواند پس از ورود دعوت را بپذیرد؛ کاربر تازه باید با ایمیل دعوت‌شده ثبت‌نام کند.</p>
        <h2>۲. نقش‌ها و مجوزها</h2><p>نقش‌ها مالک، مدیر و عضو هستند. مالک هر فضای کاری دسترسی کامل دارد. مالک می‌تواند برای نقش مدیر و عضو مجوزهای مدیریتی مانند مدیریت فضا، اعضا، تیم‌ها، حذف کارها/پروژه‌ها و گزارش‌ها را تنظیم کند. دسترسی به نسخه پشتیبان کل نصب فقط برای مالک اولیه‌ای است که اولین فضای کاری نصب را ایجاد کرده؛ زیرا آرشیو پشتیبان شامل داده همه فضاهای کاری است.</p>
        <h2>۳. صفحه‌ها و کار روزانه</h2><ul><li><b>نمای کلی:</b> جمع‌بندی کارها، موعدها و فعالیت‌ها.</li><li><b>کارهای من / همه کارها:</b> ساخت، ویرایش، واگذاری چندمسئولی، فیلتر و پیگیری وظایف.</li><li><b>کانبان و تقویم:</b> جابه‌جایی وضعیت و مرور موعدها.</li><li><b>پروژه‌ها و تیم‌ها:</b> گروه‌بندی خروجی‌ها و مدیریت عضویت.</li><li><b>گزارش عملکرد:</b> آمار روزانه/هفتگی و زمان ثبت‌شده.</li><li><b>تأییدها:</b> بازبینی کارهای ارسال‌شده برای تأیید.</li><li><b>کارهای تکرارشونده و قالب‌ها:</b> خودکارسازی کارهای تکراری و شروع از ساختارهای آماده.</li><li><b>برد ایده‌ها، فایل‌ها، یادداشت‌ها و گفت‌وگو:</b> نگهداری دانش و هماهنگی مشترک.</li></ul>
        <h2>۴. زمان‌سنج، قالب و پیش‌نیاز</h2><p>هر کاربر هم‌زمان یک زمان‌سنج فعال دارد. زمان‌های ثبت‌شده در گزارش‌ها جمع می‌شوند. قالب‌ها عنوان، شرح، اولویت، برآورد، مسئولان، تیم/پروژه و چک‌لیست پیش‌فرض دارند. پیش‌نیازها مانع تکمیل کار تا زمان تکمیل وابستگی‌ها می‌شوند. درخواست تأیید، کار را برای بررسی ارسال می‌کند و مدیر/مالک می‌تواند تأیید یا رد کند.</p>
        <h2>۵. کارهای تکرارشونده و برنامه‌ریز</h2><p>قانون روزانه، هفتگی یا ماهانه تعریف کنید. برنامه‌ریز داخلی تا وقتی BottleNeck روشن است، موعدها را بررسی و کارهای سررسیدشده را تولید می‌کند. زمان تکرار با منطقه زمانی UTC محاسبه می‌شود؛ منطقه زمانی فضای کاری قابل تنظیم نیست.</p>
        <h2>۶. برد ایده‌های مشترک</h2><p>برای هر موضوع یک برد بسازید و کارت یادداشت، متن، پیوند یا پیوند کار اضافه کنید. کارت را با سربرگ جابه‌جا کنید. تغییرات در رویدادهای فضای کاری ثبت می‌شود و به اعضای دیگر از طریق WebSocket می‌رسد. چند نفر می‌توانند کارت‌های مختلف را هم‌زمان تغییر دهند؛ ویرایش هم‌زمان محتوای یک کارت/یادداشت هنوز ادغام کاراکتری ندارد و آخرین ذخیره برنده است.</p>
        <h2>۷. فایل‌ها، پوشه‌ها و اشتراک امن</h2><p>در فضای مشترک پوشه بسازید، فایل تا ۵۰ مگابایت آپلود کنید یا متن Markdown ذخیره کنید. نوار پیشرفت، انتقال فایل را نشان می‌دهد. فایل‌ها خارج از ریشه عمومی وب در <code>data/shared</code> نگهداری می‌شوند و دانلود از مسیر احراز هویت‌شده انجام می‌شود. انواع مجاز شامل PDF، تصاویر رایج، TXT/MD/CSV، Office، ZIP، JSON و SVG است.</p><p>سطح دسترسی هر مورد می‌تواند همه اعضای فضای کار، فقط اعضای یک تیم یا محافظت با گذرواژه باشد. محدودیت پوشه والد به زیرمجموعه‌ها نیز اعمال می‌شود. مالک می‌تواند برای نقش‌های مالک/مدیر/عضو مجوز مشاهده و ویرایش جداگانه تنظیم کند. لینک کپی‌شده عمومی اینترنتی نیست؛ فرد باید وارد همان فضای کاری باشد و مجوز لازم یا گذرواژه را داشته باشد. گذرواژه را جدا از لینک ارسال کنید.</p>
        <h2>۸. یادداشت Markdown</h2><p>یادداشت‌ها به‌صورت Markdown ذخیره می‌شوند. پیش‌نمایش از GFM شامل تیتر، تأکید، فهرست، چک‌لیست، جدول، نقل‌قول، پیوند و بلوک کد پشتیبانی می‌کند. HTML خروجی با DOMPurify پاک‌سازی می‌شود. برای پیش‌نمایش غنی باید CDNهای marked و DOMPurify در دسترس مرورگر باشند؛ متن منبع حتی بدون CDN ذخیره می‌شود.</p>
        <h2>۹. گفت‌وگوی تیمی و فعالیت</h2><p>کانال عمومی فضای کاری و کانال‌های اختصاصی هر تیم وجود دارد. فقط اعضای همان تیم به کانال تیم دسترسی دارند. پیام‌ها و تغییرات کار، برد، فایل و پوشه در گزارش فعالیت ثبت می‌شوند. حضور اعضا حدود هر ۱۲ ثانیه تازه می‌شود؛ رویدادهای مشترک از WebSocket احراز هویت‌شده دریافت می‌شوند.</p>
        <h2>۱۰. امنیت حساب</h2><p>گذرواژه با PBKDF2-HMAC-SHA256 هش می‌شود و نشست در کوکی HttpOnly با عمر پیش‌فرض ۱۴ روز نگهداری می‌شود. تأیید دومرحله‌ای TOTP را از تنظیمات فعال کنید و ۱۰ کد بازیابی یک‌بارمصرف را هنگام راه‌اندازی در جای امن ذخیره کنید. هر کد بازیابی فقط یک‌بار استفاده می‌شود؛ تلاش کد دومرحله‌ای پس از ۵ بار ناموفق قفل می‌شود. اگر کدهای بازیابی را گم کنید و به برنامه TOTP دسترسی نداشته باشید، بازیابی دستی از سمت مدیر سرور لازم است.</p>
        <h2>۱۱. بازیابی گذرواژه و ایمیل</h2><p>برای ارسال خودکار لینک بازیابی و اعلان‌ها باید SMTP در تنظیمات محیط سرور تعریف شود. اگر SMTP تنظیم نباشد، درخواست عمومی پاسخ یکسان می‌دهد و لینک به ایمیل ارسال نمی‌شود. مالک/مدیر می‌تواند از مدیریت اعضا لینک بازیابی ۳۰ دقیقه‌ای بسازد و آن را از راه امن به عضو بدهد. لینک یک‌بارمصرف است و با تغییر گذرواژه، نشست‌های قبلی باطل می‌شوند.</p>
        <h2>۱۲. پشتیبان‌گیری</h2><p>اولین مالک نصب می‌تواند از تنظیمات نسخه پشتیبان دستی بسازد. برنامه پشتیبان خودکار را هر ۲۴ ساعت اجرا می‌کند (قابل تنظیم) و به‌طور پیش‌فرض ۱۴ نسخه آخر را نگه می‌دارد. فایل ZIP شامل SQLite، پیوست‌ها، فایل‌های مشترک و manifest است. برای بازیابی، سرور را متوقف کنید، از پوشه data فعلی نسخه جدا بگیرید، ZIP را در ریشه برنامه استخراج و مسیرهای <code>data/bottleneck.sqlite3</code>، <code>data/uploads</code> و <code>data/shared</code> را بازیابی کنید؛ سپس برنامه را اجرا کنید.</p>
        <h2>۱۳. SMTP، HTTPS و شبکه</h2><p>برای ایمیل متغیرهای <code>BOTTLENECK_SMTP_HOST</code>، <code>BOTTLENECK_SMTP_PORT</code>، <code>BOTTLENECK_SMTP_FROM</code> و در صورت نیاز نام کاربری/گذرواژه را تنظیم کنید. برای HTTPS می‌توانید گواهی و کلید را با <code>BOTTLENECK_SSL_CERTFILE</code> و <code>BOTTLENECK_SSL_KEYFILE</code> به لانچر بدهید. بدون HTTPS، برنامه فقط برای شبکه محلی مورد اعتماد در نظر گرفته شده است؛ پورت ۱۹۳۹ را به اینترنت فوروارد نکنید.</p>
        <h2>۱۴. محدودیت‌های نسخه MVP</h2><ul><li>پشتیبان‌گیری داخل نصب و نگهداری محلی است؛ کپی خارج از دستگاه یا فضای ابری خودکار نیست.</li><li>ارسال ایمیل تنها با SMTP تنظیم‌شده کار می‌کند؛ تأیید ایمیل و دامنه ارسال درون برنامه وجود ندارد.</li><li>کدهای TOTP در پایگاه داده نصب نگهداری می‌شوند؛ از پوشه data محافظت فیزیکی و دسترسی فایل انجام دهید.</li><li>فایل‌ها اسکن ضدبدافزار نمی‌شوند. فایل‌های ناشناس را باز نکنید.</li><li>پیش‌نمایش غنی Markdown به CDNهای خارجی وابسته است.</li><li>هم‌ویرایشی کاراکتر به کاراکتر و تاریخچه نسخه یادداشت وجود ندارد.</li><li>گزارش‌ها و اجرای قواعد تکرار بر اساس UTC هستند.</li><li>این نسخه برای استفاده تیمی روی LAN/شبکه خصوصی آماده شده؛ برای انتشار عمومی اینترنتی، reverse proxy سخت‌سازی‌شده، HTTPS معتبر، فایروال، پشتیبان خارج از میزبان و ارزیابی امنیتی مستقل لازم است.</li></ul>
        <h2>۱۵. نسخه‌ها</h2><h3>v0.6.0 · MVP admin and reliability</h3><ul><li>چند فضای کاری برای هر حساب و انتخاب/تعویض فضای فعال.</li><li>مجوزهای قابل تنظیم برای نقش‌های مدیر و عضو.</li><li>مجوز خواندن/نوشتن بر اساس نقش برای فایل‌ها و پوشه‌های مشترک.</li><li>ورود دومرحله‌ای TOTP با ۱۰ کد بازیابی یک‌بارمصرف و محدودیت تلاش.</li><li>لینک بازنشانی گذرواژه با انقضای ۳۰ دقیقه و ارسال SMTP اختیاری.</li><li>اتصال رویدادهای احراز هویت‌شده از طریق WebSocket.</li><li>پشتیبان‌گیری خودکار/دستی از پایگاه داده و فایل‌ها و نگهداری نسخه‌های اخیر.</li><li>تنظیمات اعلان ایمیلی، راه‌اندازی HTTPS و مستندات نصب/بازیابی.</li></ul>
        <h3>v0.5.0 · فضای مشترک و دانش تیمی</h3><p>برد ایده، فایل‌ها و پوشه‌های مشترک، یادداشت Markdown، سطوح دسترسی workspace/team/password، بارگذاری با نوار پیشرفت، گفت‌وگوی تیمی و گزارش فعالیت.</p>
        <h3>v0.4.0 · بهره‌وری</h3><p>زمان‌سنج، گزارش روزانه/هفتگی، کار تکرارشونده، قالب، پیش‌نیاز، تأیید و وضعیت سفارشی.</p>
        <h3>v0.3.0 · همکاری و LAN</h3><p>چند مسئول، چک‌لیست، پیوست، اعلان، عضویت تیم، راه‌اندازی شبکه محلی و امضای سازنده.</p>
        <h3>v0.2.x · پایه سرور</h3><p>ثبت‌نام، نشست سروری، پروژه، کارها، SQLite و رفع اشکال نصب ویندوز.</p>
        <h2>۱۶. میان‌برها</h2><ul><li><code>N</code> ساخت کار جدید.</li><li><code>Ctrl + K</code> تمرکز روی جست‌وجو.</li><li><code>Esc</code> بستن پنجره باز.</li><li>دکمه راهنما، تور شروع را دوباره اجرا می‌کند.</li></ul>
      </article>`;
  }
  function renderSettings() {
    const urls = state.network?.urls?.length ? state.network.urls.map(url=>`<div class="network-address"><code>${esc(url)}</code><button data-copy="${esc(url)}" title="کپی"><i data-lucide="copy"></i></button></div>`).join('') : `<p class="form-hint">IP شبکه در دسترس نیست؛ اتصال localhost همچنان فعال است.</p>`;
    const sec = state.security || {};
    const pref = state.notificationPrefs || {email_enabled:0,assigned_enabled:1,mentions_enabled:1,deadlines_enabled:1};
    const roleLabels = {"workspace.manage":"مدیریت فضای کاری","members.invite":"دعوت اعضا","members.manage":"مدیریت اعضا","teams.manage":"مدیریت تیم‌ها","backups.manage":"پشتیبان‌گیری","permissions.manage":"مدیریت مجوزها","shared.manage":"مدیریت فضای مشترک","reports.view":"مشاهده گزارش‌ها","tasks.delete":"حذف کارها","projects.delete":"حذف پروژه‌ها"};
    const permissionRows = (state.rolePermissions||[]).filter(x=>x.role!=='owner');
    const permissionsUi = isOwner() ? `<section class="panel status-settings"><div class="panel-heading"><h2>مجوزهای نقش‌ها</h2><small>کنترل دسترسی مدیر و عضو</small></div><form id="rolePermissionsForm" class="permission-matrix">${['admin','member'].map(role=>`<div class="permission-role"><strong>${roleLabel(role)}</strong>${Object.keys(roleLabels).map(key=>{const item=permissionRows.find(x=>x.role===role&&x.permission_key===key);return `<label class="permission-check"><input type="checkbox" name="${role}:${key}" ${item?.allowed?'checked':''}/><span>${roleLabels[key]}</span></label>`;}).join('')}</div>`).join('')}<div class="modal-footer"><button class="primary-button" type="submit">ذخیره مجوزها</button></div></form><p class="form-hint">مالک همیشه دسترسی کامل دارد. تغییر مجوزهای مدیر ممکن است دسترسی مدیریتی را محدود کند.</p></section>` : '';
    const backupUi = (isAdmin() && sec.instanceAdmin) ? `<section class="panel status-settings"><div class="panel-heading"><h2>پشتیبان‌گیری خودکار و دستی</h2><button class="primary-button" data-action="make-backup"><i data-lucide="archive"></i> ساخت پشتیبان</button></div><p class="form-hint">پشتیبان شامل پایگاه داده و فایل‌های بارگذاری‌شده است. زمان‌بندی خودکار هر ${faNum(state.backups?.intervalHours||24)} ساعت و نگهداری ${faNum(state.backups?.retention||14)} نسخه آخر.</p><div class="backup-list">${(state.backups?.items||[]).map(b=>`<div class="backup-row"><span><strong>${esc(b.filename)}</strong><small>${fmtTime(b.created_at)} · ${b.is_automatic?'خودکار':'دستی'} · ${faNum(Math.round(b.size_bytes/1024))} کیلوبایت</small></span><a class="secondary-button" href="/api/backups/${esc(b.id)}/download">دریافت</a></div>`).join('')||empty('archive','هنوز نسخه پشتیبانی ندارید','با اولین اجرای زمان‌بندی یا ساخت دستی، نسخه پشتیبان در اینجا دیده می‌شود.')}</div></section>` : '';
    return `${heading('تنظیمات','امنیت حساب، فضاهای کاری، مجوزها و سلامت داده‌ها.')}
      <div class="settings-grid"><section class="panel settings-card"><div class="settings-icon"><i data-lucide="user-round"></i></div><h2>اطلاعات شخصی</h2><p>نام نمایشی شما در فعالیت‌ها، اعلان‌ها و کارها نمایش داده می‌شود.</p><form id="profileForm" class="form-stack"><label class="field"><span>نام نمایشی</span><input id="profileNameInput" required minlength="2" maxlength="80" value="${esc(state.me.name)}" /></label><label class="field"><span>ایمیل حساب</span><input disabled value="${esc(state.me.email)}" /></label><button class="secondary-button" type="submit">ذخیره تغییرات</button></form></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="network"></i></div><h2>دسترسی شبکه محلی</h2><p>از دستگاه‌های دیگر متصل به همین شبکه Wi-Fi یا LAN، یکی از این نشانی‌ها را باز کنید.</p><div class="setting-data"><span>وضعیت</span><strong class="live-indicator">سرور در حال اجرا</strong></div>${urls}<div class="network-address"><code>http://127.0.0.1:1939</code><button data-copy="http://127.0.0.1:1939"><i data-lucide="copy"></i></button></div><p class="form-hint">برای HTTPS، مسیر گواهی و کلید را در متغیرهای BOTTLENECK_SSL_CERTFILE و BOTTLENECK_SSL_KEYFILE تنظیم کنید.</p></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="database"></i></div><h2>نسخه و داده‌ها</h2><p>اطلاعات فضا روی سرور میزبان ذخیره می‌شود. از پوشه data و backups مراقبت کنید.</p><div class="setting-data"><span>نسخه</span><strong>BottleNeck v${VERSION}</strong></div><div class="setting-data"><span>پایگاه داده</span><code>data/bottleneck.sqlite3</code></div><span class="version-tag">SQLite · FastAPI · WebSocket · LAN :1939</span></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="shield-check"></i></div><h2>امنیت حساب</h2><p>برای ورود دومرحله‌ای از Google Authenticator، 1Password یا برنامه TOTP سازگار استفاده کنید.</p><div class="setting-data"><span>تأیید دومرحله‌ای</span><strong>${sec.twoFactorEnabled?'فعال':'غیرفعال'}</strong></div>${sec.twoFactorEnabled?'<button class="danger-button" data-action="disable-2fa">غیرفعال‌سازی تأیید دومرحله‌ای</button>':'<button class="secondary-button" data-action="setup-2fa">راه‌اندازی تأیید دومرحله‌ای</button>'}<p class="form-hint">کلید و کدهای بازیابی را محرمانه نگه دارید. هر کد بازیابی فقط یک‌بار قابل استفاده است. کدهای باقی‌مانده: ${faNum(sec.recoveryCodesRemaining||0)}</p></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="mail"></i></div><h2>اعلان‌های ایمیلی</h2><p>${sec.emailConfigured?'ارسال ایمیل روی سرور تنظیم شده است.':'برای ارسال ایمیل، متغیرهای SMTP را در محیط سرور تنظیم کنید.'}</p><form id="notificationPrefsForm" class="form-stack"><label class="permission-check"><input type="checkbox" name="email_enabled" ${pref.email_enabled?'checked':''}/><span>ارسال اعلان به ایمیل من</span></label><label class="permission-check"><input type="checkbox" name="assigned_enabled" ${pref.assigned_enabled?'checked':''}/><span>واگذاری کار</span></label><label class="permission-check"><input type="checkbox" name="mentions_enabled" ${pref.mentions_enabled?'checked':''}/><span>اشاره و گفتگو</span></label><label class="permission-check"><input type="checkbox" name="deadlines_enabled" ${pref.deadlines_enabled?'checked':''}/><span>یادآوری موعدها</span></label><button class="secondary-button" type="submit">ذخیره تنظیمات اعلان</button></form></section></div>
      ${permissionsUi}${backupUi}
      ${isAdmin()?`<section class="panel status-settings"><div class="panel-heading"><h2>نام‌گذاری وضعیت‌ها</h2><small>گردش کار پنج‌مرحله‌ای</small></div><form id="statusLabelsForm" class="status-label-grid">${STATUSES.map(st=>{const custom=statusOf(st.id);return `<label class="field"><span>${esc(st.label)} · نام نمایشی</span><input name="label-${st.id}" maxlength="32" required value="${esc(custom.label)}" /></label><label class="field"><span>رنگ</span><select name="color-${st.id}">${['neutral','blue','gold','red','green','purple'].map(c=>`<option value="${c}" ${custom.color===c?'selected':''}>${({neutral:'خنثی',blue:'آبی',gold:'طلایی',red:'قرمز',green:'سبز',purple:'بنفش'})[c]}</option>`).join('')}</select></label>`;}).join('')}<div class="modal-footer"><button class="primary-button" type="submit">ذخیره نام وضعیت‌ها</button></div></form></section>`:''}
      <div class="danger-zone"><div><strong>خروج از حساب</strong><p>نشست فعلی این مرورگر بسته می‌شود. داده‌های فضای کاری حذف نمی‌شوند.</p></div><button class="danger-button" data-action="logout"><i data-lucide="log-out"></i> خروج امن</button></div>`;
  }

  function openTaskEditor(task = null) {
    const editing = !!task;
    const assigneeIds = task?.assigneeIds || [];
    const users = state.users.map(u=>`<option value="${esc(u.id)}" ${assigneeIds.includes(u.id)?'selected':''}>${esc(u.name)} · ${roleLabel(u.role)}</option>`).join('');
    const body = `<form id="taskEditor" class="form-stack"><input type="hidden" id="editTaskId" value="${esc(task?.id||'')}" />
      <label class="field"><span>عنوان کار <b>*</b></span><input id="editTaskTitle" required minlength="2" maxlength="180" value="${esc(task?.title||'')}" placeholder="خروجی مشخصی که باید انجام شود" /></label>
      <label class="field"><span>توضیحات</span><textarea id="editTaskDescription" rows="3" maxlength="12000" placeholder="شرح کار و خروجی مورد انتظار">${esc(task?.description||'')}</textarea></label>
      <div class="form-grid"><label class="field field-wide"><span>مسئولان (برای انتخاب چند نفر، Ctrl را نگه دارید)</span><select id="editTaskAssignees" multiple>${users}</select></label>
      <label class="field"><span>تیم</span><select id="editTaskTeam"><option value="">بدون تیم</option>${state.teams.map(t=>`<option value="${esc(t.id)}" ${task?.teamId===t.id?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label>
      <label class="field"><span>پروژه</span><select id="editTaskProject"><option value="">بدون پروژه</option>${state.projects.map(p=>`<option value="${esc(p.id)}" ${task?.projectId===p.id?'selected':''}>${esc(p.name)}</option>`).join('')}</select></label>
      <label class="field"><span>وضعیت</span><select id="editTaskStatus">${STATUSES.map(s=>`<option value="${s.id}" ${task?.status===s.id?'selected':''}>${esc(statusOf(s.id).label)}</option>`).join('')}</select></label>
      <label class="field"><span>اولویت</span><select id="editTaskPriority">${PRIORITIES.map(p=>`<option value="${p.id}" ${task?.priority===p.id?'selected':(!task&&p.id==='medium')?'selected':''}>${p.label}</option>`).join('')}</select></label>
      <label class="field"><span>موعد انجام</span><input id="editTaskDue" type="date" value="${esc(task?.dueDate||'')}" /></label>
      <label class="field"><span>برآورد زمان (ساعت)</span><input id="editTaskEstimate" type="number" min="0" step="0.5" value="${task?.estimate ?? ''}" /></label></div>
      <div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button" type="submit"><i data-lucide="check"></i>${editing?'ذخیره تغییرات':'ثبت کار'}</button></div></form>`;
    showModal(editing ? 'ویرایش کار' : 'ثبت کار جدید', body, 'مدیریت وظیفه');
  }
  async function openTaskDetail(taskId) {
    const task = state.tasks.find(t=>t.id===taskId); if (!task) return;
    state.modalTaskId = taskId;
    showModal(task.title, `<div class="empty-state"><i data-lucide="loader-circle"></i>در حال دریافت جزئیات کار...</div>`, 'جزئیات کار');
    try {
      const [comments, checklist, attachments, timeData, dependencyData, approvals] = await Promise.all([
        api(`/api/tasks/${taskId}/comments`), api(`/api/tasks/${taskId}/checklist`), api(`/api/tasks/${taskId}/attachments`),
        api(`/api/tasks/${taskId}/time`), api(`/api/tasks/${taskId}/dependencies`), api(`/api/tasks/${taskId}/approvals`)
      ]);
      const people = task.assignees?.map(u=>`<span>${esc(u.name)}</span>`).join('') || '<span>بدون مسئول</span>';
      const canDelete = isAdmin() || task.createdBy === state.me.id;
      const ownTimer = timeData.items.find(x=>!x.ended_at && x.user_id===state.me.id);
      const depIds = dependencyData.items.map(x=>x.id);
      const timeItems = timeData.items.map(x=>`<div class="time-entry-row"><strong>${esc(x.user_name)}</strong><span>${fmtTime(x.started_at)}${x.ended_at?' تا '+fmtTime(x.ended_at):' · فعال'}</span><b>${formatDuration(x.duration_seconds ?? Math.max(0,Math.floor((Date.now()-new Date(x.started_at).getTime())/1000)))}</b></div>`).join('');
      const approvalItems = approvals.map(a=>`<div class="approval-row"><div><strong>${a.status==='pending'?'در انتظار بررسی':a.status==='approved'?'تأیید شده':'نیازمند اصلاح'}</strong><small>درخواست‌دهنده: ${esc(a.requester_name||'')} · ${fmtTime(a.requested_at)}</small>${a.comment?`<p>${esc(a.comment)}</p>`:''}</div>${isAdmin()&&a.status==='pending'?`<span class="approval-actions"><button class="secondary-button" data-approval="approved" data-approval-id="${esc(a.id)}">تأیید</button><button class="danger-button" data-approval="rejected" data-approval-id="${esc(a.id)}">رد</button></span>`:''}</div>`).join('');
      const body = `<div class="detail-meta">${statusPill(task.status)}${priorityPill(task.priority)}<span class="quiet-tag">موعد: ${fmtDate(task.dueDate)}</span></div>
        <div class="detail-info-grid"><div class="detail-info"><span>مسئولان</span><div class="task-assignee-chips">${people}</div></div><div class="detail-info"><span>تیم / پروژه</span><strong>${esc(task.teamName||'بدون تیم')} · ${esc(task.projectName||'بدون پروژه')}</strong></div><div class="detail-info"><span>برآورد</span><strong>${task.estimate == null ? 'ثبت نشده' : `${faNum(task.estimate)} ساعت`}</strong></div><div class="detail-info"><span>پیشرفت چک‌لیست</span><strong>${faNum(checklist.filter(x=>x.is_done).length)} از ${faNum(checklist.length)}</strong></div></div>
        <div class="detail-description">${esc(task.description||'توضیحی ثبت نشده است.')}</div>
        <section class="detail-section"><div class="detail-section-head"><h3>چک‌لیست</h3><small>${faNum(checklist.filter(x=>x.is_done).length)}/${faNum(checklist.length)} تکمیل</small></div><div class="checklist-list">${checklist.map(c=>`<label class="checklist-item ${c.is_done?'done':''}"><input type="checkbox" data-checklist-toggle="${esc(c.id)}" ${c.is_done?'checked':''}><span>${esc(c.title)}</span><button type="button" class="icon-button subtle" data-delete-checklist="${esc(c.id)}" aria-label="حذف"><i data-lucide="x"></i></button></label>`).join('') || '<p class="form-hint">هنوز موردی ثبت نشده است.</p>'}</div><form id="checklistForm" class="checklist-add"><input name="title" required maxlength="240" placeholder="قدم بعدی را بنویسید..." /><button class="secondary-button" type="submit"><i data-lucide="plus"></i> افزودن</button></form></section>
        <section class="detail-section"><div class="detail-section-head"><h3>فایل‌های پیوست</h3><small>حداکثر ۱۰ مگابایت برای هر فایل</small></div><div class="attachment-list">${attachments.map(a=>`<div class="attachment-item"><i data-lucide="file"></i><div class="attachment-meta"><strong>${esc(a.original_name)}</strong><small>${formatBytes(a.size_bytes)} · ${esc(a.uploader_name||'')}</small></div><a class="icon-button" href="/api/attachments/${esc(a.id)}/download" title="دریافت"><i data-lucide="download"></i></a>${(isAdmin()||a.uploaded_by===state.me.id)?`<button class="icon-button" data-delete-attachment="${esc(a.id)}" title="حذف"><i data-lucide="trash-2"></i></button>`:''}</div>`).join('') || '<p class="form-hint">هنوز فایلی پیوست نشده است.</p>'}</div><div class="upload-row"><input id="attachmentInput" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.txt,.csv,.doc,.docx,.xls,.xlsx,.zip" /><span class="form-hint">PDF، تصویر، Office، CSV، TXT و ZIP</span></div></section>
        <section class="detail-section"><div class="detail-section-head"><h3>زمان‌سنج</h3><strong>${formatDuration(timeData.totalSeconds||0)} ثبت‌شده</strong></div>
          <div class="timer-control">${ownTimer?`<span class="timer-live"><i data-lucide="timer"></i> زمان‌سنج شما فعال است</span><button class="danger-button" data-stop-timer="${esc(ownTimer.id)}"><i data-lucide="square"></i> توقف زمان‌سنج</button>`:`<span class="form-hint">زمان کار روی این وظیفه را ثبت کنید.</span><button class="secondary-button" data-start-timer="${esc(taskId)}"><i data-lucide="play"></i> شروع زمان‌سنج</button>`}</div>
          <div class="time-entry-list">${timeItems||'<p class="form-hint">هنوز زمانی ثبت نشده است.</p>'}</div></section>
        <section class="detail-section"><div class="detail-section-head"><h3>پیش‌نیازها</h3><small>${faNum(dependencyData.items.length)} مورد</small></div>
          <form id="dependencyForm" data-task-id="${esc(taskId)}" class="form-stack"><label class="field"><span>این کار به کدام کارها وابسته است؟</span><select id="dependencySelect" multiple>${dependencyData.options.map(x=>`<option value="${esc(x.id)}" ${depIds.includes(x.id)?'selected':''}>${esc(x.title)} · ${esc(statusOf(x.status).label)}</option>`).join('')}</select></label><p class="form-hint">تا وقتی همه پیش‌نیازها تکمیل نشده باشند، این کار به وضعیت تکمیل‌شده نمی‌رود.</p><button class="secondary-button" type="submit">ذخیره پیش‌نیازها</button></form></section>
        <section class="detail-section"><div class="detail-section-head"><h3>تأیید نهایی</h3><small>گردش کار بازبینی</small></div>
          ${approvalItems||'<p class="form-hint">هنوز درخواستی ثبت نشده است.</p>'}
          ${!approvals.some(a=>a.status==='pending')&&task.status!=='done'?`<button class="secondary-button" data-request-approval="${esc(taskId)}"><i data-lucide="send"></i> ارسال برای تأیید</button>`:''}</section>
        <section class="detail-section"><div class="detail-section-head"><h3>گفت‌وگو</h3><small>${faNum(comments.length)} یادداشت</small></div><div class="comment-list">${comments.map(c=>`<div class="comment-item"><strong>${esc(c.user_name)}</strong><p>${esc(c.body)}</p><small>${fmtTime(c.created_at)}</small></div>`).join('') || '<p class="form-hint">هنوز یادداشتی ثبت نشده است.</p>'}</div><form id="commentForm" class="comment-form"><textarea name="body" rows="2" maxlength="5000" required placeholder="یادداشت یا توضیحی برای اعضای تیم بنویسید..."></textarea><button class="primary-button" type="submit"><i data-lucide="send"></i> ارسال</button></form></section>
        <div class="modal-footer">${canDelete?'<button class="danger-button" data-delete-task><i data-lucide="trash-2"></i> حذف کار</button>':''}<span class="spacer"></span><button class="secondary-button" data-close-modal>بستن</button><button class="primary-button" data-edit-task><i data-lucide="pencil"></i> ویرایش کار</button></div>`;
      $('modalTitle').textContent = task.title; $('modalBody').innerHTML = body; iconRefresh();
    } catch (e) { $('modalBody').innerHTML = `<p class="auth-error">${esc(e.message)}</p>`; }
  }
  function formatBytes(bytes) { if (bytes < 1024) return `${faNum(bytes)} بایت`; if (bytes < 1024*1024) return `${(bytes/1024).toFixed(1)} KB`; return `${(bytes/1024/1024).toFixed(1)} MB`; }
  async function saveTask(form) {
    const id = $('editTaskId').value;
    const ids = [...$('editTaskAssignees').selectedOptions].map(o=>o.value);
    const payload = { title: $('editTaskTitle').value.trim(), description: $('editTaskDescription').value.trim(),
      assignee_ids: ids, team_id: $('editTaskTeam').value || null, project_id: $('editTaskProject').value || null,
      status: $('editTaskStatus').value, priority: $('editTaskPriority').value, due_date: $('editTaskDue').value || null,
      estimate: $('editTaskEstimate').value === '' ? null : Number($('editTaskEstimate').value) };
    await api(id ? `/api/tasks/${id}` : '/api/tasks', { method: id ? 'PATCH' : 'POST', body: payload });
    closeModal(); await refreshWorkspace(true); toast(id ? 'تغییرات کار ذخیره شد.' : 'کار جدید ثبت شد.');
  }
  async function changeTaskStatus(taskId, status) {
    const t = state.tasks.find(x=>x.id===taskId); if (!t) return;
    await api(`/api/tasks/${taskId}`, { method:'PATCH', body:{ title:t.title, description:t.description, status, priority:t.priority,
      assignee_ids:t.assigneeIds||[], team_id:t.teamId, project_id:t.projectId, due_date:t.dueDate, estimate:t.estimate } });
    await refreshWorkspace(true); toast('وضعیت کار ذخیره شد.');
  }
  async function saveProject(projectId = null) {
    const payload = { name:$('projectNameInput').value.trim(), description:$('projectDescriptionInput').value.trim(), color:$('projectColorInput').value };
    await api(projectId?`/api/projects/${projectId}`:'/api/projects',{method:projectId?'PATCH':'POST',body:payload});
    closeModal(); await refreshWorkspace(true); toast(projectId?'پروژه ویرایش شد.':'پروژه ساخته شد.');
  }
  function openRecurringEditor() {
    const body=`<form id="recurringEditor" class="form-stack"><label class="field"><span>عنوان کار</span><input name="title" required minlength="2" maxlength="180" placeholder="مثلاً بررسی هفتگی موجودی" /></label><label class="field"><span>توضیحات</span><textarea name="description" rows="2"></textarea></label><div class="form-grid"><label class="field"><span>تناوب</span><select name="cadence"><option value="daily">روزانه</option><option value="weekly" selected>هفتگی</option><option value="monthly">ماهانه</option></select></label><label class="field"><span>هر چند دوره؟</span><input name="interval_count" type="number" min="1" max="90" value="1" required /></label><label class="field"><span>اولین اجرا</span><input name="next_run_on" type="date" value="${todayISO()}" required /></label><label class="field"><span>موعد چند روز بعد؟</span><input name="due_offset_days" type="number" min="0" max="365" value="0" /></label><label class="field"><span>اولویت</span><select name="priority">${PRIORITIES.map(x=>`<option value="${x.id}" ${x.id==='medium'?'selected':''}>${x.label}</option>`).join('')}</select></label><label class="field"><span>پروژه</span><select name="project_id"><option value="">بدون پروژه</option>${state.projects.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><label class="field field-wide"><span>مسئولان</span><select name="assignee_ids" multiple>${state.users.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label></div><div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ساخت قانون تکرار</button></div></form>`;
    showModal('قانون کار تکرارشونده',body,'برنامه‌ریزی');
  }
  function openTemplateEditor() {
    const body=`<form id="templateEditor" class="form-stack"><label class="field"><span>نام قالب</span><input name="name" required minlength="2" maxlength="100" placeholder="مثلاً انتشار مقاله وبلاگ" /></label><label class="field"><span>عنوان کار پیش‌فرض</span><input name="title" required minlength="2" maxlength="180" /></label><label class="field"><span>توضیحات</span><textarea name="description" rows="3"></textarea></label><label class="field"><span>چک‌لیست اولیه (هر مورد در یک خط)</span><textarea name="checklist" rows="4" placeholder="تحقیق و جمع‌آوری منابع&#10;نگارش نسخه اولیه&#10;بازبینی نهایی"></textarea></label><div class="form-grid"><label class="field"><span>اولویت</span><select name="priority">${PRIORITIES.map(x=>`<option value="${x.id}" ${x.id==='medium'?'selected':''}>${x.label}</option>`).join('')}</select></label><label class="field"><span>برآورد ساعت</span><input name="estimate" type="number" min="0" step="0.5" /></label><label class="field"><span>پروژه</span><select name="project_id"><option value="">بدون پروژه</option>${state.projects.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><label class="field"><span>تیم</span><select name="team_id"><option value="">بدون تیم</option>${state.teams.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><label class="field field-wide"><span>مسئولان پیش‌فرض</span><select name="assignee_ids" multiple>${state.users.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label></div><div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ذخیره قالب</button></div></form>`;
    showModal('ساخت قالب کار',body,'استانداردسازی فرایند');
  }
  function openProjectEditor(project = null) {
    const body = `<form id="projectEditor" class="form-stack"><label class="field"><span>نام پروژه</span><input id="projectNameInput" required minlength="2" maxlength="120" value="${esc(project?.name||'')}" /></label><label class="field"><span>توضیحات</span><textarea id="projectDescriptionInput" rows="3" maxlength="3000">${esc(project?.description||'')}</textarea></label><label class="field"><span>رنگ نشانه</span><select id="projectColorInput"><option value="rust">آجری</option><option value="green">سبز</option><option value="blue">آبی خاکستری</option><option value="gold">طلایی</option></select></label><div class="modal-footer"><button class="secondary-button" type="button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">${project?'ذخیره':'ساخت پروژه'}</button></div></form>`;
    showModal(project?'ویرایش پروژه':'پروژه جدید',body,'هدف مشترک'); $('projectEditor').dataset.projectId=project?.id || ''; if(project) $('projectColorInput').value=project.color;
  }
  function openTeamEditor(team = null) {
    const body = `<form id="teamEditor" class="form-stack"><label class="field"><span>نام تیم</span><input id="teamNameInput" required minlength="2" maxlength="80" value="${esc(team?.name||'')}" /></label><label class="field"><span>توضیحات</span><textarea id="teamDescriptionInput" rows="3" maxlength="1000">${esc(team?.description||'')}</textarea></label><div class="modal-footer"><button class="secondary-button" type="button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ساخت تیم</button></div></form>`;
    showModal('ساخت تیم جدید',body,'ساختار همکاری');
  }
  function openInviteEditor() {
    const body = `<form id="inviteEditor" class="form-stack"><label class="field"><span>ایمیل همکار</span><input id="inviteEmailInput" required type="email" placeholder="colleague@company.com" /></label><label class="field"><span>سطح دسترسی</span><select id="inviteRoleInput"><option value="member">عضو</option><option value="admin">مدیر</option></select></label><p class="form-hint">لینک دعوت ۷ روز اعتبار دارد. آن را کپی کنید و برای همکارتان بفرستید.</p><div class="modal-footer"><button class="secondary-button" type="button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ساخت لینک دعوت</button></div></form>`;
    showModal('دعوت همکار',body,'دعوت به همکاری');
  }
  function openManageTeam(teamId) {
    const team = state.teams.find(t=>t.id===teamId); if(!team) return;
    const list = state.users.map(u=>`<label class="team-member-row"><input type="checkbox" name="member" value="${esc(u.id)}" ${(team.memberIds||[]).includes(u.id)?'checked':''}><div class="member-info"><strong>${esc(u.name)}</strong><small>${esc(u.email)}</small></div>${rolePill(u.role)}</label>`).join('');
    showModal(`اعضای تیم ${team.name}`,`<form id="teamMembersForm"><div class="team-members-checks">${list}</div><div class="modal-footer"><button class="secondary-button" type="button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">ذخیره اعضا</button></div></form>`,'مدیریت عضویت'); $('teamMembersForm').dataset.teamId=teamId;
  }
  function openBoardItemEditor(item=null) {
    const body=`<form id="boardItemForm" class="form-stack" data-item-id="${esc(item?.id||'')}"><div class="form-grid"><label class="field"><span>نوع کارت</span><select name="item_type"><option value="note" ${item?.type==='note'?'selected':''}>یادداشت چسبان</option><option value="text" ${item?.type==='text'?'selected':''}>متن ساده</option><option value="link" ${item?.type==='link'?'selected':''}>پیوند</option><option value="task" ${item?.type==='task'?'selected':''}>اتصال به کار</option></select></label><label class="field"><span>رنگ کارت</span><select name="color"><option value="butter">کرم زرد</option><option value="rose">صورتی ملایم</option><option value="sage">سبز</option><option value="blue">آبی</option><option value="paper">سفید</option></select></label></div><label class="field"><span>عنوان</span><input name="title" maxlength="180" value="${esc(item?.title||'')}" /></label><label class="field"><span>متن / توضیح</span><textarea name="content" rows="5" maxlength="12000">${esc(item?.content||'')}</textarea></label><label class="field"><span>پیوند اینترنتی (برای کارت پیوند)</span><input name="url" type="url" value="${esc(item?.url||'')}" placeholder="https://..." /></label><label class="field"><span>اتصال به کار (اختیاری)</span><select name="task_id"><option value="">بدون کار متصل</option>${state.tasks.map(t=>`<option value="${esc(t.id)}" ${item?.taskId===t.id?'selected':''}>${esc(t.title)}</option>`).join('')}</select></label><div class="form-grid"><label class="field"><span>موقعیت افقی</span><input name="x" type="number" min="0" max="10000" value="${Number(item?.x??24)}" /></label><label class="field"><span>موقعیت عمودی</span><input name="y" type="number" min="0" max="10000" value="${Number(item?.y??24)}" /></label><label class="field"><span>عرض کارت</span><input name="width" type="number" min="180" max="620" value="${Number(item?.width??260)}" /></label></div><div class="modal-footer">${item?`<button type="button" class="danger-button" data-delete-board-item="${esc(item.id)}">حذف کارت</button>`:''}<span class="spacer"></span><button type="button" class="secondary-button" data-close-modal>انصراف</button><button class="primary-button">${item?'ذخیره تغییرات':'افزودن به برد'}</button></div></form>`;
    showModal(item?'ویرایش کارت برد':'افزودن کارت به برد',body,'بوم ایده‌ها');if(item)$('boardItemForm').elements.color.value=item.color||'butter';
  }
  async function openNotifications() {
    const result = await api('/api/notifications'); state.notifications=result.items; state.unread=result.unread; $('notificationDot').classList.toggle('hidden',state.unread<1);
    const html = `<div class="panel-heading"><small>${faNum(result.unread)} خوانده‌نشده</small><button class="text-button" data-action="read-all">خواندن همه</button></div><div class="notification-list">${result.items.map(n=>`<div class="notification-item ${n.is_read?'':'unread'}" data-notification="${esc(n.id)}" data-entity="${esc(n.entity_id||'')}"><i data-lucide="${n.kind==='comment'?'message-circle':n.kind==='member'?'user-plus':'bell'}"></i><div class="notification-copy"><strong>${esc(n.title)}</strong><p>${esc(n.body)}</p><small>${fmtTime(n.created_at)}${n.actor_name?' · '+esc(n.actor_name):''}</small></div>${n.is_read?'':'<span class="unread-dot"></span>'}</div>`).join('') || empty('bell','اعلانی ندارید','واگذاری‌ها و گفتگوهای تازه در اینجا نمایش داده می‌شوند.')}</div>`;
    showModal('اعلان‌ها',html,'مرکز اعلان');
  }
  function openTour() { state.tourStep=0; $('tourBackdrop').classList.remove('hidden'); drawTour(); }
  function drawTour() {
    const [title,text] = TOUR[state.tourStep]; $('tourStepLabel').textContent=`گام ${faNum(state.tourStep+1)} از ${faNum(TOUR.length)}`;
    $('tourTitle').textContent=title; $('tourText').textContent=text;
    $('tourProgress').innerHTML=TOUR.map((_,i)=>`<span class="${i<=state.tourStep?'active':''}"></span>`).join('');
    $('tourPrev').disabled=state.tourStep===0; $('tourNext').innerHTML=state.tourStep===TOUR.length-1?'پایان <i data-lucide="check"></i>':'بعدی <i data-lucide="arrow-left"></i>'; iconRefresh();
  }
  async function finishTour() { $('tourBackdrop').classList.add('hidden'); await api('/api/me/onboarding',{method:'POST',body:{completed:true}}).catch(()=>{}); }
  async function navigate(page) { if(!PAGES[page]) return; state.page=page; if(state.page!=='my-tasks'&&state.page!=='all-tasks') state.taskFilter='all'; render(); $('sidebar').classList.remove('open');
    api('/api/presence',{method:'POST',body:{page}}).catch(()=>{});
    if(page==='settings') {
      const [network,security,permissions,backups,prefs]=await Promise.all([
        api('/api/network').catch(()=>null),api('/api/security').catch(()=>null),api('/api/permissions').catch(()=>null),
        isAdmin()?api('/api/backups').catch(()=>null):Promise.resolve(null),api('/api/notifications/preferences').catch(()=>null)
      ]);
      state.network=network;state.security=security;state.rolePermissions=permissions?.items||[];state.backups=backups;state.notificationPrefs=prefs;render();
    }
    if(page==='reports') loadReports().catch(e=>toast(e.message,'alert-circle'));
    if(page==='recurring') api('/api/recurring').then(data=>{state.recurringRules=data;render();}).catch(e=>toast(e.message,'alert-circle'));
    if(page==='templates') api('/api/templates').then(data=>{state.templates=data;render();}).catch(e=>toast(e.message,'alert-circle'));
    if(page==='shared-board') loadBoards().catch(e=>toast(e.message,'alert-circle'));
    if(page==='shared-drive'||page==='shared-notes') loadDrive(null).catch(e=>toast(e.message,'alert-circle'));
    if(page==='team-chat') loadChat().catch(e=>toast(e.message,'alert-circle'));
  }
  async function loadReports() { state.reportData=await api(`/api/reports?period=${state.reportPeriod}`); render(); }

  // Event delegation keeps dynamically-rendered views functional without inline scripts.
  document.addEventListener('click', async (event) => {
    const nav = event.target.closest('[data-page]'); if (nav) { navigate(nav.dataset.page); return; }
    const pageLink = event.target.closest('[data-page-link]'); if(pageLink){ navigate(pageLink.dataset.pageLink); return; }
    const close = event.target.closest('[data-close-modal]'); if(close){ closeModal(); return; }
    const credit = event.target.closest('[data-open-credit]'); if(credit){openCredit();return;}
    const closeCreditBtn = event.target.closest('[data-close-credit]'); if(closeCreditBtn){closeCredit();return;}
    const openTask = event.target.closest('[data-open-task]'); if(openTask){openTaskDetail(openTask.dataset.openTask);return;}
    const action = event.target.closest('[data-action]')?.dataset.action;
    if(action==='new-task'){openTaskEditor();return;}
    if(action==='make-backup'){try{const b=await api('/api/backups',{method:'POST'});toast('نسخه پشتیبان ساخته شد.','archive');state.backups=await api('/api/backups');render();}catch(e){toast(e.message,'alert-circle');}return;}
    if(action==='setup-2fa'){try{const d=await api('/api/security/totp/setup',{method:'POST'});showModal('راه‌اندازی تأیید دومرحله‌ای',`<div class="form-stack"><p class="form-hint">این کلید را در برنامه احراز هویت اضافه کنید. کدهای بازیابی را در جای امن نگه دارید؛ بعد از بستن این پنجره دوباره نمایش داده نمی‌شوند.</p><label class="field"><span>کلید محرمانه</span><input readonly value="${esc(d.secret)}" dir="ltr" /></label><label class="field"><span>پیوند TOTP</span><textarea readonly rows="2" dir="ltr">${esc(d.otpauthUri)}</textarea></label><label class="field"><span>۱۰ کد بازیابی یک‌بارمصرف</span><textarea readonly rows="5" dir="ltr" spellcheck="false">${esc((d.recoveryCodes||[]).join('\n'))}</textarea></label><form id="totpEnableForm" class="form-stack"><label class="field"><span>کد ۶ رقمی برنامه</span><input name="code" inputmode="numeric" pattern="[0-9]{6}" minlength="6" maxlength="6" required /></label><button class="primary-button">فعال‌سازی تأیید دومرحله‌ای</button></form></div>`,'امنیت حساب');}catch(e){toast(e.message,'alert-circle');}return;}
    if(action==='disable-2fa'){const password=prompt('گذرواژه حساب را وارد کنید:');if(!password)return;const code=prompt('کد ۶ رقمی برنامه احراز هویت یا کد بازیابی یک‌بارمصرف:');if(!code)return;try{await api('/api/security/totp/disable',{method:'POST',body:{password,code}});state.security=await api('/api/security');render();toast('تأیید دومرحله‌ای غیرفعال شد.');}catch(e){toast(e.message,'alert-circle');}return;}
    if(action==='new-board'){const title=prompt('نام برد تازه را وارد کنید:');if(title&&title.trim()){const b=await api('/api/boards',{method:'POST',body:{title:title.trim(),description:''}});state.activeBoardId=b.id;state.boardPassword='';await loadBoards();toast('برد تازه ساخته شد.');}return;}
    if(action==='new-board-item'){if(!state.activeBoardId){await loadBoards();}if(state.activeBoardId)openBoardItemEditor();return;}
    if(action==='new-folder'){openDriveNodeCreator('folder');return;}
    if(action==='new-note'){openMarkdownEditor(null,state.driveParentId);return;}
    if(action==='upload-shared'){const body=`<form id="sharedUploadSetupForm" class="form-stack"><p class="form-hint">فایل پیش از بارگذاری با سطح دسترسی انتخاب‌شده ذخیره می‌شود. نوار پیشرفت پس از انتخاب فایل نمایش داده خواهد شد.</p><div class="form-grid">${shareControls('uploadShare')}</div><div class="modal-footer"><button type="button" class="secondary-button" data-close-modal>انصراف</button><span class="spacer"></span><button class="primary-button">انتخاب فایل</button></div></form>`;showModal('بارگذاری فایل مشترک',body,'تنظیم دسترسی فایل');return;}
    if(action==='new-project'){openProjectEditor();return;}
    if(action==='new-team'){openTeamEditor();return;}
    if(action==='invite'){openInviteEditor();return;}
    if(action==='new-recurring'){openRecurringEditor();return;}
    if(action==='new-template'){openTemplateEditor();return;}
    if(action==='logout'){await api('/api/auth/logout',{method:'POST'}).catch(()=>{});showAuth();toast('از حساب خارج شدید.','log-out');return;}
    if(action==='read-all'){await api('/api/notifications/read-all',{method:'POST'});await refreshWorkspace(true);await openNotifications();return;}
    const filter = event.target.closest('[data-task-filter]'); if(filter){state.taskFilter=filter.dataset.taskFilter;render();return;}
    const cal = event.target.closest('[data-calendar]'); if(cal){state.month.setMonth(state.month.getMonth()+(cal.dataset.calendar==='next'?1:-1));render();return;}
    const editTask = event.target.closest('[data-edit-task]'); if(editTask){const t=state.tasks.find(x=>x.id===state.modalTaskId);closeModal();if(t)openTaskEditor(t);return;}
    const deleteTask = event.target.closest('[data-delete-task]'); if(deleteTask){if(!confirm('این کار و فایل‌های پیوست آن حذف شود؟'))return;await api(`/api/tasks/${state.modalTaskId}`,{method:'DELETE'});closeModal();await refreshWorkspace(true);toast('کار حذف شد.');return;}
    const addProject = event.target.closest('[data-edit-project]'); if(addProject){const p=state.projects.find(x=>x.id===addProject.dataset.editProject);if(p)openProjectEditor(p);return;}
    const delProject = event.target.closest('[data-delete-project]'); if(delProject){if(!confirm('پروژه حذف شود؟ کارهای متصل باقی می‌مانند.'))return;await api(`/api/projects/${delProject.dataset.deleteProject}`,{method:'DELETE'});await refreshWorkspace(true);toast('پروژه حذف شد.');return;}
    const projectTasks = event.target.closest('[data-project-tasks]');if(projectTasks){state.search='';$('globalSearch').value='';state.page='all-tasks';render();document.querySelectorAll('#taskRows tr[data-open-task]').forEach(row=>{const t=state.tasks.find(x=>x.id===row.dataset.openTask);row.hidden=t?.projectId!==projectTasks.dataset.projectTasks;});return;}
    const manageTeam = event.target.closest('[data-manage-team]');if(manageTeam){openManageTeam(manageTeam.dataset.manageTeam);return;}
    const delTeam = event.target.closest('[data-delete-team]');if(delTeam){if(!confirm('تیم حذف شود؟ کارهای آن بدون تیم باقی می‌مانند.'))return;await api(`/api/teams/${delTeam.dataset.deleteTeam}`,{method:'DELETE'});await refreshWorkspace(true);toast('تیم حذف شد.');return;}
    const revoke = event.target.closest('[data-revoke-invite]');if(revoke){if(!confirm('دعوت‌نامه لغو شود؟'))return;await api(`/api/invitations/${revoke.dataset.revokeInvite}`,{method:'DELETE'});await refreshWorkspace(true);toast('دعوت‌نامه لغو شد.');return;}
    const copy = event.target.closest('[data-copy]');if(copy){await copyText(copy.dataset.copy);toast('نشانی کپی شد.','copy');return;}
    const notification = event.target.closest('[data-notification]');if(notification){const id=notification.dataset.notification,entity=notification.dataset.entity;await api(`/api/notifications/${id}/read`,{method:'PATCH'});await refreshWorkspace(true);closeModal();if(entity)openTaskDetail(entity);return;}
    const startTimer = event.target.closest('[data-start-timer]'); if(startTimer){await api(`/api/tasks/${startTimer.dataset.startTimer}/time/start`,{method:'POST'});await refreshWorkspace(true);await openTaskDetail(startTimer.dataset.startTimer);toast('زمان‌سنج شروع شد.','timer');return;}
    const stopTimer = event.target.closest('[data-stop-timer]'); if(stopTimer){await api('/api/time/stop',{method:'POST',body:{entry_id:stopTimer.dataset.stopTimer}});await refreshWorkspace(true);await openTaskDetail(state.modalTaskId);toast('زمان ثبت شد.','timer');return;}
    const requestApproval = event.target.closest('[data-request-approval]'); if(requestApproval){await api(`/api/tasks/${requestApproval.dataset.requestApproval}/approvals`,{method:'POST'});await refreshWorkspace(true);await openTaskDetail(requestApproval.dataset.requestApproval);toast('درخواست تأیید ارسال شد.','send');return;}
    const approvalAction=event.target.closest('[data-approval]'); if(approvalAction){const ok=approvalAction.dataset.approval==='approved';const note=prompt(ok?'یادداشت تأیید (اختیاری)':'دلیل نیاز به اصلاح (اختیاری)')||'';await api(`/api/approvals/${approvalAction.dataset.approvalId}`,{method:'PATCH',body:{status:approvalAction.dataset.approval,comment:note}});await refreshWorkspace(true);if(state.modalTaskId)await openTaskDetail(state.modalTaskId);toast(ok?'کار تأیید شد.':'کار برای اصلاح بازگشت.');return;}
    const toggleRecurring=event.target.closest('[data-toggle-recurring]'); if(toggleRecurring){await api(`/api/recurring/${toggleRecurring.dataset.toggleRecurring}/toggle`,{method:'PATCH'});state.recurringRules=await api('/api/recurring');render();toast('وضعیت قانون تکرار تغییر کرد.');return;}
    const deleteRecurring=event.target.closest('[data-delete-recurring]'); if(deleteRecurring){if(!confirm('این قانون تکرار حذف شود؟ کارهای قبلی باقی می‌مانند.'))return;await api(`/api/recurring/${deleteRecurring.dataset.deleteRecurring}`,{method:'DELETE'});state.recurringRules=await api('/api/recurring');render();toast('قانون حذف شد.');return;}
    const useTemplate=event.target.closest('[data-use-template]'); if(useTemplate){const task=await api(`/api/templates/${useTemplate.dataset.useTemplate}/create-task`,{method:'POST'});await refreshWorkspace(true);toast('کار از قالب ساخته شد.');openTaskDetail(task.id);return;}
    const deleteTemplate=event.target.closest('[data-delete-template]'); if(deleteTemplate){if(!confirm('قالب حذف شود؟ کارهای ساخته‌شده باقی می‌مانند.'))return;await api(`/api/templates/${deleteTemplate.dataset.deleteTemplate}`,{method:'DELETE'});state.templates=await api('/api/templates');render();toast('قالب حذف شد.');return;}
    const reportPeriod=event.target.closest('[data-report-period]'); if(reportPeriod){state.reportPeriod=reportPeriod.dataset.reportPeriod;state.reportData=null;render();await loadReports();return;}
    const deleteChecklist = event.target.closest('[data-delete-checklist]');if(deleteChecklist){await api(`/api/tasks/${state.modalTaskId}/checklist/${deleteChecklist.dataset.deleteChecklist}`,{method:'DELETE'});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);return;}
    const deleteAttachment = event.target.closest('[data-delete-attachment]');if(deleteAttachment){if(!confirm('این پیوست حذف شود؟'))return;await api(`/api/attachments/${deleteAttachment.dataset.deleteAttachment}`,{method:'DELETE'});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);return;}
    if(event.target.closest('.board-link'))return;
    const mdTab=event.target.closest('[data-md-tab]');if(mdTab){const preview=mdTab.dataset.mdTab==='preview';$('mdSource')?.classList.toggle('hidden',preview);$('mdPreview')?.classList.toggle('hidden',!preview);document.querySelectorAll('[data-md-tab]').forEach(x=>x.classList.toggle('active',x===mdTab));updateMarkdownPreview();return;}
    const editBoardItem=event.target.closest('[data-edit-board-item]');if(editBoardItem){const item=state.boardItems.find(x=>x.id===editBoardItem.dataset.editBoardItem);if(item)openBoardItemEditor(item);return;}
    const openNode=event.target.closest('[data-open-drive-node]');if(openNode){await openDriveNode(openNode.dataset.openDriveNode);return;}
    const crumb=event.target.closest('[data-drive-crumb]');if(crumb){const index=Number(crumb.dataset.driveCrumb);const target=state.driveTrail[index];state.driveTrail=state.driveTrail.slice(0,index);await loadDrive(target?.id||null,state.drivePassword);return;}
    if(event.target.closest('[data-drive-root]')){await loadDrive(null);return;}
    const shareNode=event.target.closest('[data-share-node]');if(shareNode){const node=state.driveItems.find(x=>x.id===shareNode.dataset.shareNode);if(node){if(node.locked){const pass=prompt('برای تغییر تنظیمات، گذرواژه اشتراک را وارد کنید:')||'';if(!pass)return;state.drivePassword=pass;}openShareSettings(node);}return;}
    const copyNode=event.target.closest('[data-copy-node]');if(copyNode){const link=`${location.origin}/?openNode=${encodeURIComponent(copyNode.dataset.copyNode)}`;await copyText(link);toast('پیوند داخلی کپی شد.','copy');return;}
    const downloadNode=event.target.closest('[data-download-node]');if(downloadNode){const n=state.driveItems.find(x=>x.id===downloadNode.dataset.downloadNode);let pass=state.drivePassword||'';if(n?.locked){pass=prompt('گذرواژه فایل را وارد کنید:')||'';if(!pass)return;}window.location.href=`/api/drive/nodes/${downloadNode.dataset.downloadNode}/download${pass?'?password='+encodeURIComponent(pass):''}`;return;}
    const deleteNode=event.target.closest('[data-delete-node]');if(deleteNode){if(!confirm('این مورد و در صورت پوشه‌بودن تمام محتویات آن حذف شود؟'))return;const node=state.driveItems.find(x=>x.id===deleteNode.dataset.deleteNode);if(node?.locked){const pass=prompt('برای حذف، گذرواژه اشتراک را وارد کنید:')||'';if(!pass)return;state.drivePassword=pass;}await api(`/api/drive/nodes/${deleteNode.dataset.deleteNode}${state.drivePassword?'?password='+encodeURIComponent(state.drivePassword):''}`,{method:'DELETE'});await loadDrive();toast('مورد حذف شد.');return;}
    const deleteBoardItem=event.target.closest('[data-delete-board-item]');if(deleteBoardItem){if(!confirm('این کارت از برد حذف شود؟'))return;await api(`/api/boards/${state.activeBoardId}/items/${deleteBoardItem.dataset.deleteBoardItem}`,{method:'DELETE'});closeModal();await loadBoardItems();return;}

  });

  document.addEventListener('change', async (event) => {
    const filter = event.target;
    if(filter.id==='sharedBoardSelect'){state.activeBoardId=filter.value;state.boardPassword='';await loadBoardItems('');return;}
    if(filter.id==='chatChannelSelect'){if(filter.value==='workspace'){state.chatChannel='workspace';state.chatTeamId='';}else{state.chatChannel='team';state.chatTeamId=filter.value;}await loadChat();return;}
    if(filter.id==='driveUploadInput'&&filter.files?.[0]){uploadSharedFile(filter.files[0]);filter.value='';return;}
    if(filter.id==='noteShareAccess'||filter.id==='nodeShareAccess'||filter.id==='uploadShareAccess'){
      const prefix=filter.id==='noteShareAccess'?'noteShare':filter.id==='nodeShareAccess'?'nodeShare':'uploadShare';$(`${prefix}TeamWrap`)?.classList.toggle('hidden',filter.value!=='team');$(`${prefix}PasswordWrap`)?.classList.toggle('hidden',filter.value!=='password');return;
    }
    if(filter.id==='shareEditAccess'){$('shareEditTeamWrap')?.classList.toggle('hidden',filter.value!=='team');$('shareEditPasswordWrap')?.classList.toggle('hidden',filter.value!=='password');return;}

    if(filter.id==='statusFilter'||filter.id==='teamFilter'){
      document.querySelectorAll('#taskRows tr[data-open-task]').forEach(row=>{const t=state.tasks.find(x=>x.id===row.dataset.openTask);row.hidden=!!((filter.id==='statusFilter'&&filter.value&&t?.status!==filter.value)||(filter.id==='teamFilter'&&filter.value&&t?.teamId!==filter.value)|| (filter.id==='statusFilter'&&$('teamFilter')?.value&&t?.teamId!==$('teamFilter').value));});return;
    }
    if(filter.matches('[data-checklist-toggle]')){await api(`/api/tasks/${state.modalTaskId}/checklist/${filter.dataset.checklistToggle}`,{method:'PATCH',body:{is_done:filter.checked}});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);return;}
    if(filter.id==='attachmentInput'&&filter.files?.[0]){
      const file=filter.files[0];if(file.size>10*1024*1024){toast('حجم فایل بیشتر از ۱۰ مگابایت است.','alert-circle');filter.value='';return;}
      try{await api(`/api/tasks/${state.modalTaskId}/attachments`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream','X-Filename':encodeURIComponent(file.name)},body:file});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);toast('فایل پیوست شد.','paperclip');}catch(e){toast(e.message,'alert-circle');}
    }
  });

  document.addEventListener('input',event=>{if(event.target.id==='mdSource')updateMarkdownPreview();});
  let boardPointer = null;
  $('pageContent').addEventListener('pointerdown',event=>{
    const grip=event.target.closest('[data-board-drag]'); if(!grip||event.target.closest('button'))return;
    const card=grip.closest('[data-board-item]'); const canvas=$('conceptCanvas'); if(!card||!canvas)return;
    const rect=card.getBoundingClientRect(); boardPointer={id:card.dataset.boardItem,card,dx:event.clientX-rect.left,dy:event.clientY-rect.top};
    card.setPointerCapture?.(event.pointerId); card.classList.add('is-dragging'); event.preventDefault();
  });
  $('pageContent').addEventListener('pointermove',event=>{
    if(!boardPointer)return; const canvas=$('conceptCanvas'); if(!canvas)return; const r=canvas.getBoundingClientRect();
    const x=Math.max(0,Math.min(10000,event.clientX-r.left-boardPointer.dx)); const y=Math.max(0,Math.min(10000,event.clientY-r.top-boardPointer.dy));
    boardPointer.card.style.left=x+'px'; boardPointer.card.style.top=y+'px'; boardPointer.x=x; boardPointer.y=y;
  });
  $('pageContent').addEventListener('pointerup',async()=>{
    if(!boardPointer)return; const d=boardPointer;boardPointer=null;d.card.classList.remove('is-dragging');
    const item=state.boardItems.find(x=>x.id===d.id);if(!item)return;
    const payload={item_type:item.type,title:item.title,content:item.content,url:item.url||'',task_id:item.taskId||null,x:d.x??item.x,y:d.y??item.y,width:item.width||260,color:item.color||'butter'};
    try{await api(`/api/boards/${state.activeBoardId}/items/${item.id}`,{method:'PATCH',body:payload});item.x=payload.x;item.y=payload.y;}catch(e){toast(e.message,'alert-circle');await loadBoardItems();}
  });

  document.addEventListener('submit', async (event) => {
    const form=event.target; event.preventDefault();
    try {
      if(form.id==='taskEditor'){await saveTask(form);return;}
      if(form.id==='recurringEditor'){
        const f=form.elements;const payload={title:f.title.value.trim(),description:f.description.value.trim(),priority:f.priority.value,cadence:f.cadence.value,
          interval_count:Number(f.interval_count.value),next_run_on:f.next_run_on.value,due_offset_days:Number(f.due_offset_days.value),project_id:f.project_id.value||null,
          team_id:null,assignee_ids:[...f.assignee_ids.selectedOptions].map(x=>x.value)};
        await api('/api/recurring',{method:'POST',body:payload});closeModal();state.recurringRules=await api('/api/recurring');render();toast('قانون تکرار ساخته شد.');return;
      }
      if(form.id==='templateEditor'){
        const f=form.elements;const payload={name:f.name.value.trim(),title:f.title.value.trim(),description:f.description.value.trim(),priority:f.priority.value,
          estimate:f.estimate.value===''?null:Number(f.estimate.value),checklist:f.checklist.value.split('\n').map(x=>x.trim()).filter(Boolean),
          project_id:f.project_id.value||null,team_id:f.team_id.value||null,assignee_ids:[...f.assignee_ids.selectedOptions].map(x=>x.value)};
        await api('/api/templates',{method:'POST',body:payload});closeModal();state.templates=await api('/api/templates');render();toast('قالب ذخیره شد.');return;
      }
      if(form.id==='dependencyForm'){
        const ids=[...$('dependencySelect').selectedOptions].map(x=>x.value);await api(`/api/tasks/${form.dataset.taskId}/dependencies`,{method:'PUT',body:{dependency_ids:ids}});await refreshWorkspace(true);await openTaskDetail(form.dataset.taskId);toast('پیش‌نیازها ذخیره شدند.');return;
      }
      if(form.id==='statusLabelsForm'){
        const items=STATUSES.map((x,i)=>({key:x.id,label:form.elements[`label-${x.id}`].value.trim(),color:form.elements[`color-${x.id}`].value}));
        const data=await api('/api/status-labels',{method:'PUT',body:{items}});state.statusLabels=data.items;render();toast('نام وضعیت‌ها ذخیره شد.');return;
      }
      if(form.id==='projectEditor'){const projectId=$('projectEditor').dataset.projectId||null;await saveProject(projectId);return;}
      if(form.id==='teamEditor'){const payload={name:$('teamNameInput').value.trim(),description:$('teamDescriptionInput').value.trim()};await api('/api/teams',{method:'POST',body:payload});closeModal();await refreshWorkspace(true);toast('تیم ساخته شد.');return;}
      if(form.id==='inviteEditor'){
        const result=await api('/api/invitations',{method:'POST',body:{email:$('inviteEmailInput').value.trim(),role:$('inviteRoleInput').value}});
        showModal('لینک دعوت آماده است',`<p class="form-hint">این لینک را برای همکارتان بفرستید. همکار باید با همین ایمیل ثبت‌نام کند. لینک تا ۷ روز معتبر است.</p><div class="invite-link-box"><input id="inviteUrlResult" readonly value="${esc(result.inviteUrl)}" /><button type="button" class="primary-button" data-copy-invite><i data-lucide="copy"></i> کپی</button></div><div class="modal-footer"><button class="secondary-button" data-close-modal>بستن</button></div>`,'دعوت به همکاری');await refreshWorkspace(true);return;
      }
      if(form.id==='teamMembersForm'){const teamId=form.dataset.teamId;if(!teamId)throw new Error('شناسه تیم پیدا نشد.');const ids=[...form.querySelectorAll('input[name="member"]:checked')].map(x=>x.value);await api(`/api/teams/${teamId}/members`,{method:'PUT',body:{member_ids:ids}});closeModal();await refreshWorkspace(true);toast('اعضای تیم ذخیره شدند.');return;}
      if(form.id==='checklistForm'){const title=form.elements.title.value.trim();if(!title)return;await api(`/api/tasks/${state.modalTaskId}/checklist`,{method:'POST',body:{title}});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);return;}
      if(form.id==='commentForm'){const body=form.elements.body.value.trim();if(!body)return;await api(`/api/tasks/${state.modalTaskId}/comments`,{method:'POST',body:{body}});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);toast('یادداشت ثبت شد.');return;}
      if(form.id==='sharedUploadSetupForm'){
        const f=form.elements;const accessMode=f.access_mode.value;const password=f.password.value||'';
        if(accessMode==='team'&&!f.team_id.value)throw new Error('برای اشتراک تیمی، یک تیم انتخاب کنید.');
        if(accessMode==='password'&&password.length<8)throw new Error('گذرواژه اشتراک باید دست‌کم ۸ نویسه باشد.');
        state.uploadShareSettings={access_mode:accessMode,team_id:f.team_id.value||null,password:password};closeModal();$('driveUploadInput')?.click();return;
      }
      if(form.id==='boardItemForm'){
        const f=form.elements;const payload={item_type:f.item_type.value,title:f.title.value.trim(),content:f.content.value.trim(),url:f.url.value.trim(),task_id:f.task_id.value||null,x:Number(f.x.value||24),y:Number(f.y.value||24),width:Number(f.width.value||260),color:f.color.value};
        const id=form.dataset.itemId; if(id)await api(`/api/boards/${state.activeBoardId}/items/${id}`,{method:'PATCH',body:payload});else await api(`/api/boards/${state.activeBoardId}/items`,{method:'POST',body:payload});
        closeModal();await loadBoardItems();toast(id?'کارت به‌روزرسانی شد.':'کارت به برد اضافه شد.');return;
      }
      if(form.id==='sharedNoteForm'){
        const f=form.elements;const id=form.dataset.nodeId;const payload={title:f.title.value.trim(),content:f.content.value};
        if(id)await api(`/api/drive/nodes/${id}${state.drivePassword?'?password='+encodeURIComponent(state.drivePassword):''}`,{method:'PATCH',body:payload});
        else {const share={node_type:'text',title:payload.title,content:payload.content,parent_id:form.dataset.parentId||null,parent_password:state.drivePassword||null,access_mode:f.access_mode.value,team_id:f.team_id.value||null,password:f.password.value||null};await api('/api/drive/nodes',{method:'POST',body:share});}
        closeModal();await loadDrive(state.driveParentId,state.drivePassword);toast('یادداشت ذخیره شد.');return;
      }
      if(form.id==='driveNodeForm'){
        const f=form.elements;const body={node_type:f.node_type.value,title:f.title.value.trim(),content:f.content?.value||'',parent_id:state.driveParentId,parent_password:state.drivePassword||null,access_mode:f.access_mode.value,team_id:f.team_id.value||null,password:f.password.value||null};
        await api('/api/drive/nodes',{method:'POST',body});closeModal();await loadDrive();toast(body.node_type==='folder'?'پوشه ساخته شد.':'یادداشت ساخته شد.');return;
      }
      if(form.id==='shareSettingsForm'){
        const f=form.elements;const body={access_mode:f.access_mode.value,team_id:f.team_id.value||null,password:f.password.value||null};
        await api(`/api/drive/nodes/${form.dataset.nodeId}${state.drivePassword?'?password='+encodeURIComponent(state.drivePassword):''}`,{method:'PATCH',body});
        if(isOwner()&&f['acl-read-admin']){const items=['admin','member'].map(role=>({role,can_read:f[`acl-read-${role}`].checked,can_write:f[`acl-write-${role}`].checked}));await api(`/api/drive/nodes/${form.dataset.nodeId}/role-permissions`,{method:'PUT',body:{items}});}
        closeModal();await loadDrive();toast('تنظیمات اشتراک ذخیره شد.');return;
      }
      if(form.id==='chatComposeForm'){
        const body=form.elements.body.value.trim();if(!body)return;await api('/api/chat',{method:'POST',body:{body,channel_type:state.chatChannel,team_id:state.chatChannel==='team'?state.chatTeamId:null}});form.reset();await loadChat();return;
      }
      if(form.id==='totpEnableForm'){await api('/api/security/totp/enable',{method:'POST',body:{code:form.elements.code.value.trim()}});closeModal();state.security=await api('/api/security');render();toast('تأیید دومرحله‌ای فعال شد.','shield-check');return;}
      if(form.id==='rolePermissionsForm'){const items=[];for(const role of ['admin','member'])for(const permission of Object.keys({"workspace.manage":1,"members.invite":1,"members.manage":1,"teams.manage":1,"backups.manage":1,"permissions.manage":1,"shared.manage":1,"reports.view":1,"tasks.delete":1,"projects.delete":1})){items.push({role,permission,allowed:!!form.elements[`${role}:${permission}`]?.checked});}await api('/api/permissions',{method:'PUT',body:{items}});state.rolePermissions=(await api('/api/permissions')).items;toast('مجوزهای نقش‌ها ذخیره شد.');render();return;}
      if(form.id==='notificationPrefsForm'){const f=form.elements;await api('/api/notifications/preferences',{method:'PUT',body:{email_enabled:f.email_enabled.checked,assigned_enabled:f.assigned_enabled.checked,mentions_enabled:f.mentions_enabled.checked,deadlines_enabled:f.deadlines_enabled.checked}});state.notificationPrefs=await api('/api/notifications/preferences');toast('تنظیمات اعلان ذخیره شد.');return;}
      if(form.id==='profileForm'){await api('/api/me',{method:'PATCH',body:{name:$('profileNameInput').value.trim()}});await refreshWorkspace(true);toast('نام نمایشی ذخیره شد.');return;}
      if(form.id==='loginForm'){await signIn(form);return;}
      if(form.id==='registerForm'){await register(form);return;}
    } catch(e){toast(e.message,'alert-circle');}
  });

  document.querySelectorAll('[data-auth-tab]').forEach(b=>b.addEventListener('click',()=>setAuthTab(b.dataset.authTab)));
  document.querySelectorAll('[data-switch-auth]').forEach(b=>b.addEventListener('click',()=>setAuthTab(b.dataset.switchAuth)));
  $('registerForm').addEventListener('input',()=>{});
  $('logoutButton').addEventListener('click',async()=>{await api('/api/auth/logout',{method:'POST'}).catch(()=>{});showAuth();});
  $('workspaceSelect')?.addEventListener('change',e=>switchWorkspaceOrCreate(e.target.value));
  document.querySelector('[data-forgot-password]')?.addEventListener('click',async()=>{const email=$('loginEmail').value.trim()||prompt('ایمیل حساب را وارد کنید:');if(!email)return;try{const result=await api('/api/auth/password-reset/request',{method:'POST',body:{email}});showAuthError(result.message);}catch(e){showAuthError(e.message);}});
  $('globalCreate').addEventListener('click',()=>openTaskEditor());
  $('notificationButton').addEventListener('click',()=>openNotifications().catch(e=>toast(e.message,'alert-circle')));
  $('helpButton').addEventListener('click',openTour);
  $('focusButton').addEventListener('click',()=>navigate('my-tasks'));
  $('mobileMenu').addEventListener('click',()=>$('sidebar').classList.toggle('open'));
  $('globalSearch').addEventListener('input',e=>{state.search=e.target.value.trim();if(!['my-tasks','all-tasks','board'].includes(state.page))state.page='all-tasks';render();});
  $('globalSearch').addEventListener('keydown',e=>{if(e.key==='Escape'){e.target.value='';state.search='';render();e.target.blur();}});
  $('modalBackdrop').addEventListener('click',e=>{if(e.target===$('modalBackdrop'))closeModal();});
  $('creditBackdrop').addEventListener('click',e=>{if(e.target===$('creditBackdrop'))closeCredit();});
  $('tourNext').addEventListener('click',()=>{if(state.tourStep<TOUR.length-1){state.tourStep++;drawTour();}else finishTour();});
  $('tourPrev').addEventListener('click',()=>{if(state.tourStep>0){state.tourStep--;drawTour();}});
  $('tourSkip').addEventListener('click',finishTour); $('tourClose').addEventListener('click',finishTour);
  $('copyInviteLink')?.addEventListener('click',()=>{});
  $('modalBody').addEventListener('click',async e=>{const b=e.target.closest('[data-copy-invite]');if(b){try{await copyText($('inviteUrlResult').value);toast('لینک دعوت کپی شد.','copy');}catch(err){toast(err.message,'alert-circle');}}});
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('globalSearch').focus();}
    if(e.key.toLowerCase()==='n'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!e.ctrlKey&&!e.metaKey){e.preventDefault();openTaskEditor();}
    if(e.key==='Escape'){closeModal();closeCredit();}
  });
  let draggedTaskId=null;
  $('pageContent').addEventListener('dragstart',e=>{const card=e.target.closest('[data-drag-task]');if(!card)return;draggedTaskId=card.dataset.dragTask;card.classList.add('dragging');e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',draggedTaskId);});
  $('pageContent').addEventListener('dragend',()=>{draggedTaskId=null;document.querySelectorAll('.kanban-card').forEach(c=>c.classList.remove('dragging'));document.querySelectorAll('.kanban-column').forEach(c=>c.classList.remove('drag-over'));});
  $('pageContent').addEventListener('dragover',e=>{const col=e.target.closest('[data-drop-status]');if(col){e.preventDefault();col.classList.add('drag-over');}});
  $('pageContent').addEventListener('dragleave',e=>{const col=e.target.closest('[data-drop-status]');if(col&&!col.contains(e.relatedTarget))col.classList.remove('drag-over');});
  $('pageContent').addEventListener('drop',async e=>{const col=e.target.closest('[data-drop-status]');if(!col)return;e.preventDefault();const id=e.dataTransfer.getData('text/plain')||draggedTaskId;if(!id)return;try{await changeTaskStatus(id,col.dataset.dropStatus);}catch(err){toast(err.message,'alert-circle');await refreshWorkspace(true);}});
  // Apply invite-mode presentation before a session is checked.
  const inviteCode = new URLSearchParams(location.search).get('invite');
  if(inviteCode){setAuthTab('register');$('workspaceNameField').classList.add('hidden');$('inviteHint').classList.remove('hidden');}
  // A password-reset link is single-use and expires after 30 minutes.
  const resetToken = new URLSearchParams(location.search).get('reset');
  if(resetToken){
    history.replaceState({},'',location.pathname);showAuth();
    const newPassword=prompt('گذرواژه تازه را وارد کنید (حداقل ۸ نویسه):');
    if(newPassword){api('/api/auth/password-reset/complete',{method:'POST',body:{token:resetToken,password:newPassword}}).then(()=>showAuthError('گذرواژه تغییر کرد. اکنون وارد شوید.')).catch(e=>showAuthError(e.message));}
  }else{
    // Restore an existing session, otherwise leave the registration screen ready.
    startWorkspace().catch(()=>showAuth());
  }
  iconRefresh();
})();
