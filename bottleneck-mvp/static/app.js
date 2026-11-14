/* BottleNeck v0.4.0
   Creator credit requested by the project owner: «ساخته شده با عشق توسط ژلوفن».
   Telegram: https://t.me/jelofen1962 | Phone: +989109721962
*/
(() => {
  'use strict';
  const VERSION = '0.4.0';
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
    handbook: 'راهنمای استفاده', settings: 'تنظیمات'
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
    ['راهنما و پشتیبان‌گیری', 'راهنمای کامل داخل برنامه قرار دارد. پایگاه داده و فایل‌ها روی رایانه میزبان ذخیره می‌شوند؛ به‌طور منظم از پوشه data پشتیبان بگیرید.']
  ];
  const $ = (id) => document.getElementById(id);
  const state = { me: null, tasks: [], users: [], teams: [], projects: [], activity: [], invitations: [], notifications: [],
    recurringRules: [], templates: [], statusLabels: [], pendingApprovals: [], activeTimer: null,
    reportData: null, reportPeriod: 'weekly', unread: 0, page: 'overview', search: '', eventCursor: 0,
    pollHandle: null, month: new Date(), taskFilter: 'all', modalTaskId: null, tourStep: 0, network: null };

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  const faNum = (value) => Number(value || 0).toLocaleString('fa-IR');
  const roleLabel = (r) => ({ owner: 'مالک', admin: 'مدیر', member: 'عضو' }[r] || 'عضو');
  const statusOf = (id) => { const base=STATUSES.find(x => x.id === id) || STATUSES[0]; const custom=(state.statusLabels||[]).find(x=>x.key===base.id); return custom ? {...base,label:custom.label,color:custom.color} : base; };
  const priorityOf = (id) => PRIORITIES.find(x => x.id === id) || PRIORITIES[2];
  const userOf = (id) => state.users.find(u => u.id === id) || { id: '', name: 'بدون مسئول', email: '', role: 'member' };
  const projectOf = (id) => state.projects.find(p => p.id === id) || { name: 'بدون پروژه' };
  const teamOf = (id) => state.teams.find(t => t.id === id) || { name: 'بدون تیم' };
  const isAdmin = () => state.me && ['owner', 'admin'].includes(state.me.role);
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
    stopPolling(); $('appShell').classList.add('hidden'); $('authScreen').classList.remove('hidden');
    setAuthTab(new URLSearchParams(location.search).has('invite') ? 'register' : 'login');
  }
  async function signIn(form) {
    const email = $('loginEmail').value.trim(); const password = $('loginPassword').value;
    try { await api('/api/auth/login', { method: 'POST', body: { email, password } }); await startWorkspace(); }
    catch (e) { showAuthError(e.message); }
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
      Object.assign(state, data); state.unread = Number(data.unreadNotifications || 0); state.eventCursor = Number(data.eventCursor || 0);
      $('authScreen').classList.add('hidden'); $('appShell').classList.remove('hidden');
      $('workspaceNameLabel').textContent = state.me.workspaceName;
      $('workspaceInitial').textContent = initials(state.me.workspaceName).slice(0, 1);
      $('workspaceRoleLabel').textContent = `${roleLabel(state.me.role)} · فضای مشترک`;
      $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role);
      $('profileAvatar').textContent = initials(state.me.name).slice(0, 1); $('welcomeName')?.textContent;
      $('globalSearch').value = state.search;
      $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role); $('profileAvatar').textContent = initials(state.me.name).slice(0, 1);
      render(); startPolling();
      if (!state.me.onboardingCompleted) openTour();
      else if (isNew) toast('حساب شما آماده است. به BottleNeck خوش آمدید.');
    } catch (e) { showAuth(); if (isNew) showAuthError(e.message); }
  }
  async function refreshWorkspace(quiet = false) {
    const data = await api('/api/bootstrap');
    Object.assign(state, data); state.unread = Number(data.unreadNotifications || 0); state.eventCursor = Math.max(state.eventCursor, Number(data.eventCursor || 0));
    $('profileName').textContent = state.me.name; $('profileRole').textContent = roleLabel(state.me.role); $('profileAvatar').textContent = initials(state.me.name).slice(0, 1);
    render();
    if (!quiet) toast('فضای کار به‌روز شد.');
  }
  function startPolling() {
    stopPolling();
    state.pollHandle = window.setInterval(async () => {
      try {
        const result = await api(`/api/updates?after_id=${state.eventCursor}`);
        const events = result.events || [];
        state.eventCursor = Math.max(state.eventCursor, Number(result.cursor || 0));
        const external = events.filter(e => e.user_id && e.user_id !== state.me.id);
        if (events.length) {
          const before = state.unread;
          const data = await api('/api/bootstrap'); Object.assign(state, data); state.unread = Number(data.unreadNotifications || 0); state.eventCursor = Math.max(state.eventCursor, Number(data.eventCursor || 0));
          render();
          if (external.length) toast('به‌روزرسانی تازه از هم‌تیمی‌ها دریافت شد.', 'refresh-cw');
          if (state.unread > before) toast('اعلان تازه دارید.', 'bell');
        }
      } catch (_) { /* temporary LAN interruptions are retried on the next tick */ }
    }, 3500);
  }
  function stopPolling() { if (state.pollHandle) window.clearInterval(state.pollHandle); state.pollHandle = null; }

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
      recurring: renderRecurring, templates: renderTemplates, handbook: renderHandbook, settings: renderSettings
    }[state.page] || renderOverview;
    $('pageContent').innerHTML = renderer(); iconRefresh();
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
    return `${heading('راهنمای استفاده','راهنمای کامل صفحه‌ها، گردش کار و تغییرات نسخه‌ها.')}
      <article class="panel handbook">
        <p class="eyebrow">BottleNeck · راهنمای محصول</p><h2>از BottleNeck چطور استفاده کنیم؟</h2><p>BottleNeck فضای کاری مشترک برای ثبت مسئولیت، پیگیری پیشرفت و هماهنگی تیم است. همه اعضا به یک پایگاه داده روی رایانه میزبان متصل می‌شوند؛ بنابراین هر تغییر پس از ذخیره، برای دیگران نیز قابل مشاهده خواهد بود.</p>
        <div class="handbook-callout">نکته شبکه: رایانه میزبان باید روشن باشد و BottleNeck روی آن اجرا شود. سایر دستگاه‌ها از آدرس LAN همان رایانه و پورت ۱۹۳۹ وارد می‌شوند.</div>
        <h2>۱. ورود و ساخت فضای کار</h2><ol><li>اولین نفر از زبانه «ساخت فضای کار» نام، ایمیل، گذرواژه و نام فضای کار را وارد می‌کند.</li><li>حساب اول با نقش مالک ساخته می‌شود.</li><li>اعضای بعدی با لینک دعوت و همان ایمیلی که دعوت شده‌اند ثبت‌نام می‌کنند.</li><li>نشست ورود در کوکی HttpOnly نگهداری و سمت سرور بررسی می‌شود.</li></ol>
        <h2>۲. نمای کلی</h2><p>نمای کلی تعداد کارها، کارهای فعال، کارهای تکمیل‌شده، کارهای عقب‌افتاده، موعدهای نزدیک، فعالیت‌های تازه و بار کاری اعضا را نشان می‌دهد. فضای کاری تازه با آمار صفر شروع می‌شود؛ داده آزمایشی ساختگی وارد نمی‌شود.</p>
        <h2>۳. کارها و مسئولیت‌ها</h2><p>در فرم کار، عنوان و توضیحات را وارد کنید. می‌توانید بیش از یک مسئول انتخاب کنید، سپس تیم، پروژه، وضعیت، اولویت، موعد و برآورد ساعت را تعیین کنید. انتخاب چند مسئول به معنی همکاری مشترک روی یک خروجی است؛ همه آنها اعلان واگذاری دریافت می‌کنند.</p><ul><li><b>در صف:</b> کار ثبت شده اما شروع نشده است.</li><li><b>در حال انجام:</b> یکی از اعضا در حال پیش‌بردن آن است.</li><li><b>در بررسی:</b> خروجی آماده بازبینی است.</li><li><b>متوقف‌شده:</b> تا رفع مانع امکان ادامه نیست.</li><li><b>تکمیل‌شده:</b> خروجی نهایی شده است.</li></ul>
        <h2>۴. جزئیات کار، چک‌لیست و پیوست‌ها</h2><p>با بازکردن هر کار، جزئیات و گفت‌وگو را می‌بینید. از چک‌لیست برای تقسیم کار به قدم‌های کوچک استفاده کنید. هر مورد قابل تیک‌زدن و حذف است. در بخش فایل‌ها می‌توانید تصویر، PDF، اسناد Office، CSV، TXT و ZIP تا سقف ۱۰ مگابایت بارگذاری کنید. فایل‌ها به‌صورت خصوصی در پوشه داده سرور ذخیره می‌شوند و دریافت آنها نیازمند ورود و عضویت در همان فضای کاری است.</p>
        <h2>۵. برد کانبان</h2><p>کارت‌ها را بین ستون‌ها بکشید. تغییر وضعیت در پایگاه داده ثبت می‌شود. به کمک به‌روزرسانی دوره‌ای هر ۳٫۵ ثانیه، دستگاه‌های دیگر نیز تغییرات را دریافت می‌کنند؛ برای وضعیت سریع‌تر، صفحه را دستی تازه کنید.</p>
        <h2>۶. تقویم و پروژه‌ها</h2><p>تقویم فقط کارهایی را نشان می‌دهد که موعد دارند. پروژه‌ها گروه‌بندی هدف‌محور هستند و درصد پیشرفت از تعداد کارهای تکمیل‌شده در پروژه به کل کارهای آن محاسبه می‌شود.</p>
        <h2>۷. تیم‌ها و مدیریت اعضا</h2><p>مالک و مدیر می‌توانند تیم بسازند، اعضا را به هر تیم اضافه یا از آن خارج کنند، دعوت‌نامه بسازند و دعوت‌های باز را لغو کنند. عضویت در تیم و مسئولیت کار دو مفهوم مستقل‌اند. عضو عادی می‌تواند کار بسازد و گفتگو کند؛ اما مدیریت ساختار تیم و دعوت‌نامه‌ها مخصوص مدیران است.</p>
        <h2>۸. اعلان‌ها و همگام‌سازی</h2><p>اعلان برای واگذاری کار، یادداشت تازه روی کار و پیوستن عضو جدید ساخته می‌شود. زنگوله بالای صفحه تعداد اعلان‌های خوانده‌نشده را نشان می‌دهد. وضعیت و داده‌های مشترک از API سرور دریافت می‌شوند و از localStorage به‌عنوان منبع اصلی استفاده نمی‌شود.</p>
        <h2>۹. شبکه محلی</h2><p>سرور روی <code>0.0.0.0:1939</code> گوش می‌دهد. از بخش تنظیمات می‌توانید IPهای شناسایی‌شده رایانه میزبان را ببینید. در ویندوز، شبکه باید روی Private باشد و در صورت مسدودشدن اتصال، قانون فایروال خصوصی برای TCP پورت ۱۹۳۹ ایجاد کنید. این راه‌اندازی برای شبکه محلی مورد اعتماد است، نه انتشار مستقیم روی اینترنت.</p>
        <h2>۱۰. نسخه‌ها</h2><h3>v0.4.0 · بهره‌وری و گردش کار</h3><ul><li>زمان‌سنج مستقل برای هر عضو و هر کار؛ هر کاربر هم‌زمان فقط یک زمان‌سنج فعال دارد.</li><li>گزارش روزانه و هفتگی از ایجاد و تکمیل کارها و زمان ثبت‌شده به تفکیک عضو و پروژه.</li><li>قوانین تکرار روزانه، هفتگی و ماهانه؛ کارهای سررسیدشده هنگام ورود اعضا به فضای کار ساخته می‌شوند.</li><li>قالب‌های کار با شرح، برآورد، مسئولان و چک‌لیست پیش‌فرض.</li><li>وابستگی بین کارها با جلوگیری از چرخه و جلوگیری از تکمیل زودهنگام.</li><li>درخواست بازبینی و تصمیم تأیید یا بازگشت برای اصلاح.</li><li>تغییر نام و رنگ پنج وضعیت پایه برای هر فضای کار.</li><li>رابط کاربری در نمایشگرهای دسکتاپ با مقیاس تقریبی ۱۲۰٪ و بازگشت به مقیاس عادی در نمایشگرهای کوچک.</li></ul>
        <h3>v0.3.0 · همکاری تیمی و شبکه محلی</h3><ul><li>چک‌لیست و زیرکار برای هر وظیفه.</li><li>بارگذاری و دریافت پیوست با دسترسی احراز هویت‌شده.</li><li>اعلان‌های درون‌برنامه‌ای و علامت‌گذاری به‌عنوان خوانده‌شده.</li><li>چند مسئول برای هر کار.</li><li>مدیریت عضویت اعضا در تیم‌ها.</li><li>همگام‌سازی تغییرات در شبکه از طریق polling رویدادهای سرور.</li><li>راه‌اندازی LAN با IP شبکه و پورت ۱۹۳۹.</li><li>پنجره امضای سازنده با پیوند تلگرام و شماره تماس.</li></ul>
        <h3>v0.2.1 · رفع مشکل نصب ویندوز</h3><p>استفاده از Python 3.12 و حذف وابستگی‌های اختیاری Uvicorn برای جلوگیری از ساخت بومی PyYAML در نصب ویندوز.</p>
        <h3>v0.2.0 · پایه سرور</h3><p>حساب‌های سرور، فضای کاری مشترک، نشست امن، دعوت‌نامه، کارها، پروژه‌ها و فعالیت‌ها.</p>
        <h2>۱۱. پشتیبان‌گیری</h2><p>سرور را متوقف کنید و از کل پوشه <code>data</code> شامل فایل SQLite و پوشه uploads نسخه پشتیبان بگیرید. برای بازیابی، نسخه پشتیبان را در همان مسیر قرار دهید و برنامه را دوباره اجرا کنید. فایل دیتابیس را هنگام نوشتن فعال، با کپی ساده جابه‌جا نکنید.</p>
        <h2>۱۲. میان‌برها</h2><ul><li><code>N</code> ساخت کار جدید.</li><li><code>Ctrl + K</code> تمرکز روی جست‌وجو.</li><li><code>Esc</code> بستن پنجره باز.</li><li>کلید راهنما، تور شروع را دوباره اجرا می‌کند.</li></ul>
        <h2>۱۳. مرزهای فعلی MVP</h2><p>ارسال ایمیل خودکار، بازیابی گذرواژه، احراز هویت دومرحله‌ای، چند فضای کار برای هر کاربر، اعلان push و اتصال WebSocket هنوز پیاده‌سازی نشده‌اند. کارهای زمان‌بندی‌شده هنگام بازشدن فضای کار و با روشن بودن سرور ساخته می‌شوند؛ برای زمان‌بندی مستقل در پس‌زمینه باید در آینده سرویس زمان‌بند دائمی اضافه شود. رنگ وضعیت‌ها قابل شخصی‌سازی است اما تعداد وضعیت‌های پایه در این نسخه پنج مورد ثابت است.</p>
      </article>`;
  }
  function renderSettings() {
    // Network details are refreshed by navigate() after this view is rendered.
    const urls = state.network?.urls?.length ? state.network.urls.map(url=>`<div class="network-address"><code>${esc(url)}</code><button data-copy="${esc(url)}" title="کپی"><i data-lucide="copy"></i></button></div>`).join('') : `<p class="form-hint">IP شبکه در دسترس نیست؛ اتصال localhost همچنان فعال است.</p>`;
    return `${heading('تنظیمات','اطلاعات حساب، نسخه برنامه و دسترسی در شبکه محلی.')}
      <div class="settings-grid"><section class="panel settings-card"><div class="settings-icon"><i data-lucide="user-round"></i></div><h2>اطلاعات شخصی</h2><p>نام نمایشی شما در فعالیت‌ها، اعلان‌ها و کارها نمایش داده می‌شود.</p><form id="profileForm" class="form-stack"><label class="field"><span>نام نمایشی</span><input id="profileNameInput" required minlength="2" maxlength="80" value="${esc(state.me.name)}" /></label><label class="field"><span>ایمیل حساب</span><input disabled value="${esc(state.me.email)}" /></label><button class="secondary-button" type="submit">ذخیره تغییرات</button></form></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="network"></i></div><h2>دسترسی شبکه محلی</h2><p>از دستگاه‌های دیگر متصل به همین شبکه Wi-Fi یا LAN، یکی از این نشانی‌ها را باز کنید.</p><div class="setting-data"><span>وضعیت</span><strong class="live-indicator">سرور در حال اجرا</strong></div>${urls}<div class="network-address"><code>http://127.0.0.1:1939</code><button data-copy="http://127.0.0.1:1939"><i data-lucide="copy"></i></button></div><p class="form-hint">اگر دستگاه دیگر وصل نشد، فایروال ویندوز و نوع شبکه Private را بررسی کنید.</p></section>
      <section class="panel settings-card"><div class="settings-icon"><i data-lucide="database"></i></div><h2>نسخه و داده‌ها</h2><p>اطلاعات این فضا روی سرور میزبان ذخیره می‌شود. برای انتقال یا پشتیبان‌گیری، پوشه data را نگه دارید.</p><div class="setting-data"><span>نسخه</span><strong>BottleNeck v${VERSION}</strong></div><div class="setting-data"><span>پایگاه داده</span><code>data/bottleneck.sqlite3</code></div><span class="version-tag">SQLite · FastAPI · LAN :1939</span></section></div>
      ${isAdmin()?`<section class="panel status-settings"><div class="panel-heading"><h2>نام‌گذاری وضعیت‌ها</h2><small>گردش کار پنج‌مرحله‌ای</small></div><p class="form-hint">می‌توانید نام و رنگ هر وضعیت را متناسب با روند تیم خود تغییر دهید؛ ساختار پایه حفظ می‌شود.</p><form id="statusLabelsForm" class="status-label-grid">${STATUSES.map(st=>{const custom=statusOf(st.id);return `<label class="field"><span>${esc(st.label)} · نام نمایشی</span><input name="label-${st.id}" maxlength="32" required value="${esc(custom.label)}" /></label><label class="field"><span>رنگ</span><select name="color-${st.id}">${['neutral','blue','gold','red','green','purple'].map(c=>`<option value="${c}" ${custom.color===c?'selected':''}>${({neutral:'خنثی',blue:'آبی',gold:'طلایی',red:'قرمز',green:'سبز',purple:'بنفش'})[c]}</option>`).join('')}</select></label>`;}).join('')}<div class="modal-footer"><button class="primary-button" type="submit">ذخیره نام وضعیت‌ها</button></div></form></section>`:''}
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
    if(page==='settings') { const network=await api('/api/network').catch(()=>null); if(network){state.network=network; render();} }
    if(page==='reports') loadReports().catch(e=>toast(e.message,'alert-circle'));
    if(page==='recurring') api('/api/recurring').then(data=>{state.recurringRules=data;render();}).catch(e=>toast(e.message,'alert-circle'));
    if(page==='templates') api('/api/templates').then(data=>{state.templates=data;render();}).catch(e=>toast(e.message,'alert-circle'));
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
  });

  document.addEventListener('change', async (event) => {
    const filter = event.target;
    if(filter.id==='statusFilter'||filter.id==='teamFilter'){
      document.querySelectorAll('#taskRows tr[data-open-task]').forEach(row=>{const t=state.tasks.find(x=>x.id===row.dataset.openTask);row.hidden=!!((filter.id==='statusFilter'&&filter.value&&t?.status!==filter.value)||(filter.id==='teamFilter'&&filter.value&&t?.teamId!==filter.value)|| (filter.id==='statusFilter'&&$('teamFilter')?.value&&t?.teamId!==$('teamFilter').value));});return;
    }
    if(filter.matches('[data-checklist-toggle]')){await api(`/api/tasks/${state.modalTaskId}/checklist/${filter.dataset.checklistToggle}`,{method:'PATCH',body:{is_done:filter.checked}});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);return;}
    if(filter.id==='attachmentInput'&&filter.files?.[0]){
      const file=filter.files[0];if(file.size>10*1024*1024){toast('حجم فایل بیشتر از ۱۰ مگابایت است.','alert-circle');filter.value='';return;}
      try{await api(`/api/tasks/${state.modalTaskId}/attachments`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream','X-Filename':encodeURIComponent(file.name)},body:file});await openTaskDetail(state.modalTaskId);await refreshWorkspace(true);toast('فایل پیوست شد.','paperclip');}catch(e){toast(e.message,'alert-circle');}
    }
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
      if(form.id==='profileForm'){await api('/api/me',{method:'PATCH',body:{name:$('profileNameInput').value.trim()}});await refreshWorkspace(true);toast('نام نمایشی ذخیره شد.');return;}
      if(form.id==='loginForm'){await signIn(form);return;}
      if(form.id==='registerForm'){await register(form);return;}
    } catch(e){toast(e.message,'alert-circle');}
  });

  document.querySelectorAll('[data-auth-tab]').forEach(b=>b.addEventListener('click',()=>setAuthTab(b.dataset.authTab)));
  document.querySelectorAll('[data-switch-auth]').forEach(b=>b.addEventListener('click',()=>setAuthTab(b.dataset.switchAuth)));
  $('registerForm').addEventListener('input',()=>{});
  $('logoutButton').addEventListener('click',async()=>{await api('/api/auth/logout',{method:'POST'}).catch(()=>{});showAuth();});
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
  // Restore an existing session, otherwise leave the registration screen ready.
  startWorkspace().catch(()=>showAuth());
  iconRefresh();
})();
