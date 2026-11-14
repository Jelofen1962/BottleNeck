(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const statusMeta = {
    todo: { label: 'در صف', cls: 'todo' },
    'in-progress': { label: 'در حال انجام', cls: 'in-progress' },
    review: { label: 'در بررسی', cls: 'review' },
    blocked: { label: 'متوقف‌شده', cls: 'blocked' },
    done: { label: 'تکمیل‌شده', cls: 'done' }
  };
  const priorityMeta = {
    urgent: { label: 'فوری', cls: 'urgent' },
    high: { label: 'زیاد', cls: 'high' },
    medium: { label: 'متوسط', cls: 'medium' },
    low: { label: 'کم', cls: 'low' }
  };
  const roleNames = { owner: 'مالک', admin: 'مدیر', member: 'عضو' };
  const viewNames = {
    overview: 'نمای کلی', 'my-tasks': 'کارهای من', 'all-tasks': 'همه کارها',
    board: 'برد کانبان', calendar: 'تقویم', projects: 'پروژه‌ها', team: 'اعضای تیم',
    activity: 'گزارش فعالیت', handbook: 'راهنمای استفاده', settings: 'تنظیمات حساب'
  };
  const boardColumns = [
    { id: 'todo', label: 'در صف' }, { id: 'in-progress', label: 'در حال انجام' },
    { id: 'review', label: 'در بررسی' }, { id: 'blocked', label: 'متوقف‌شده' }, { id: 'done', label: 'تکمیل‌شده' }
  ];
  const tourSteps = [
    { view: 'overview', target: '[data-tour="overview"]', title: 'نمای کلی، نقطه شروع شماست', text: 'اینجا وضعیت واقعی فضای کاری را می‌بینید: کارهای نزدیک به موعد، موارد عقب‌افتاده، پیشرفت و آخرین تغییرات. وقتی فضای کار تازه ساخته شده باشد، آمارها از صفر شروع می‌شوند.' },
    { view: 'my-tasks', target: '[data-tour="my-tasks"]', title: 'مسئولیت‌های خودتان را جدا ببینید', text: 'در «کارهای من» فقط وظایفی نمایش داده می‌شوند که به حساب شما واگذار شده‌اند. می‌توانید کارهای باز و تکمیل‌شده را جدا کنید و فهرست را مرتب کنید.' },
    { view: 'all-tasks', target: '[data-tour="all-tasks"]', title: 'یک تصویر مشترک از همه کارها', text: 'در این صفحه کل کارهای فضای کار قرار دارد. بر اساس وضعیت، تیم یا پروژه فیلتر کنید و با بازکردن هر ردیف به جزئیات، یادداشت‌ها و ویرایش کار برسید.' },
    { view: 'board', target: '[data-tour="board"]', title: 'جریان انجام کار را روی برد ببینید', text: 'کارت‌ها بین ستون‌ها حرکت می‌کنند. یک کارت را بکشید و در ستون مقصد رها کنید؛ وضعیت جدید روی سرور ذخیره خواهد شد.' },
    { view: 'projects', target: '[data-tour="projects"]', title: 'کارهای مرتبط را در پروژه جمع کنید', text: 'پروژه یک هدف مشترک را مشخص می‌کند. بعد از ساخت پروژه، آن را هنگام ثبت کار انتخاب کنید تا پیشرفت پروژه بر اساس کارهای متصل محاسبه شود.' },
    { view: 'team', target: '[data-tour="team"]', title: 'هم‌تیمی‌ها را دعوت کنید', text: 'مدیر یا مالک می‌تواند دعوت‌نامه بسازد. لینک را کپی کنید و برای همکار بفرستید؛ همکار با همان ایمیل دعوت‌شده ثبت‌نام می‌کند و به فضای فعلی می‌پیوندد.' },
    { view: 'handbook', target: '[data-tour="handbook"]', title: 'راهنما همیشه در دسترس است', text: 'راهنمای کامل داخل برنامه، کاربرد هر صفحه، تعریف وضعیت‌ها، نکات امنیتی و تاریخچه تغییرات نسخه‌ها را توضیح می‌دهد. هر زمان نیاز داشتید می‌توانید از همین منو دوباره آن را باز کنید.' }
  ];

  let me = null;
  let data = { tasks: [], users: [], teams: [], projects: [], activity: [], invitations: [] };
  let activeView = 'overview';
  let currentFilter = { my: 'all', all: 'all' };
  let searchTerm = '';
  let calendarDate = new Date();
  let selectedTaskId = null;
  let selectedTourStep = 0;
  let draggedTaskId = null;
  let editingProjectId = null;
  let inviteCode = new URLSearchParams(location.search).get('invite') || '';

  const fa = (value) => Number(value || 0).toLocaleString('fa-IR');
  const isoToday = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };
  const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const dateObject = (iso) => iso ? new Date(`${iso}T12:00:00`) : null;
  const formatDate = (iso) => {
    const d = dateObject(iso);
    return d ? d.toLocaleDateString('fa-IR', { day: 'numeric', month: 'short' }) : 'بدون موعد';
  };
  const fullDate = (iso) => {
    const d = dateObject(iso);
    return d ? d.toLocaleDateString('fa-IR', { year: 'numeric', month: 'long', day: 'numeric' }) : 'ثبت نشده';
  };
  const formatDateTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('fa-IR', { day: 'numeric', month: 'short' }) + '، ' + d.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
  };
  const userById = (id) => data.users.find((u) => u.id === id) || null;
  const projectById = (id) => data.projects.find((p) => p.id === id) || null;
  const teamById = (id) => data.teams.find((t) => t.id === id) || null;
  const overdue = (task) => task.status !== 'done' && task.dueDate && task.dueDate < isoToday();
  const isAdmin = () => me && ['owner', 'admin'].includes(me.role);

  async function api(path, options = {}) {
    const config = { method: options.method || 'GET', credentials: 'same-origin', headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) } };
    if (options.body !== undefined) config.body = JSON.stringify(options.body);
    const response = await fetch(path, config);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : null;
    if (!response.ok) {
      const message = payload?.detail || `خطا در ارتباط با سرور (${response.status})`;
      throw new Error(Array.isArray(message) ? message.map((x) => x.msg).join('، ') : message);
    }
    return payload;
  }

  function refreshIcons() {
    if (window.lucide?.createIcons) window.lucide.createIcons({ attrs: { 'stroke-width': 1.75 } });
  }
  function toast(message, icon = 'check') {
    const node = document.createElement('div');
    node.className = 'toast';
    node.innerHTML = `<i data-lucide="${escapeHTML(icon)}"></i><span>${escapeHTML(message)}</span>`;
    $('toastRegion').appendChild(node);
    refreshIcons();
    window.setTimeout(() => {
      node.classList.add('toast-leaving');
      window.setTimeout(() => node.remove(), 240);
    }, 3000);
  }
  function showAuthError(message) {
    $('authError').textContent = message;
    $('authError').classList.remove('hidden');
  }
  function clearAuthError() {
    $('authError').textContent = '';
    $('authError').classList.add('hidden');
  }
  function switchAuth(mode) {
    clearAuthError();
    document.querySelectorAll('.auth-tab').forEach((el) => el.classList.toggle('active', el.dataset.authTab === mode));
    $('loginPanel').classList.toggle('hidden', mode !== 'login');
    $('registerPanel').classList.toggle('hidden', mode !== 'register');
    $('inviteHint').classList.toggle('hidden', !inviteCode || mode !== 'register');
    $('workspaceNameField').classList.toggle('hidden', Boolean(inviteCode));
    $('workspaceName').required = !inviteCode;
  }
  function showAuth() {
    $('authScreen').classList.remove('hidden');
    $('appShell').classList.add('hidden');
    refreshIcons();
  }
  function showApp() {
    $('authScreen').classList.add('hidden');
    $('appShell').classList.remove('hidden');
    refreshIcons();
  }

  async function hydrate() {
    const boot = await api('/api/bootstrap');
    me = boot.me;
    data = { tasks: boot.tasks || [], users: boot.users || [], teams: boot.teams || [], projects: boot.projects || [], activity: boot.activity || [], invitations: boot.invitations || [] };
    activeView = 'overview';
    currentFilter = { my: 'all', all: 'all' };
    searchTerm = '';
    $('globalSearch').value = '';
    renderIdentity();
    populateFiltersAndForm();
    showApp();
    renderAll();
    navigate('overview');
    if (!me.onboardingCompleted) startTour();
  }
  async function checkSession() {
    try {
      await hydrate();
    } catch (error) {
      if (error.message && !error.message.includes('نشست') && !error.message.includes('وارد حساب')) console.warn(error);
      showAuth();
      if (inviteCode) switchAuth('register');
    }
  }
  function renderIdentity() {
    $('workspaceNameLabel').textContent = me.workspaceName;
    $('workspaceInitial').textContent = (me.workspaceName || 'ب').trim().slice(0, 1);
    $('workspaceRoleLabel').textContent = `فضای مشترک · ${roleNames[me.role] || 'عضو'}`;
    $('profileName').textContent = me.name;
    $('profileRole').textContent = roleNames[me.role] || 'عضو';
    $('profileAvatar').textContent = (me.name || '؟').trim().slice(0, 1);
    $('welcomeName').textContent = me.name.split(' ')[0];
    $('profileNameInput').value = me.name;
    $('profileEmailInput').value = me.email;
    $('settingsWorkspaceName').textContent = me.workspaceName;
    $('settingsRole').textContent = roleNames[me.role] || 'عضو';
    $('todayLabel').textContent = new Date().toLocaleDateString('fa-IR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    $('inviteButton').classList.toggle('hidden', !isAdmin());
    $('newTeamButton').classList.toggle('hidden', !isAdmin());
    $('invitationList').closest('.invitations-panel').classList.toggle('hidden', !isAdmin());
  }
  function populateFiltersAndForm() {
    const teamFilter = $('teamFilter');
    const projectFilter = $('projectFilter');
    teamFilter.innerHTML = '<option value="all">همه تیم‌ها</option>' + data.teams.map((t) => `<option value="${escapeHTML(t.id)}">${escapeHTML(t.name)}</option>`).join('');
    projectFilter.innerHTML = '<option value="all">همه پروژه‌ها</option>' + data.projects.map((p) => `<option value="${escapeHTML(p.id)}">${escapeHTML(p.name)}</option>`).join('');
    const currentTeam = $('taskTeam').value;
    const currentProject = $('taskProject').value;
    const currentAssignee = $('taskAssignee').value;
    $('taskAssignee').innerHTML = '<option value="">بدون مسئول</option>' + data.users.map((u) => `<option value="${escapeHTML(u.id)}">${escapeHTML(u.name)}</option>`).join('');
    $('taskTeam').innerHTML = '<option value="">بدون تیم</option>' + data.teams.map((t) => `<option value="${escapeHTML(t.id)}">${escapeHTML(t.name)}</option>`).join('');
    $('taskProject').innerHTML = '<option value="">بدون پروژه</option>' + data.projects.map((p) => `<option value="${escapeHTML(p.id)}">${escapeHTML(p.name)}</option>`).join('');
    if ([...$('taskTeam').options].some((o) => o.value === currentTeam)) $('taskTeam').value = currentTeam;
    if ([...$('taskProject').options].some((o) => o.value === currentProject)) $('taskProject').value = currentProject;
    if ([...$('taskAssignee').options].some((o) => o.value === currentAssignee)) $('taskAssignee').value = currentAssignee;
  }

  function statusHTML(status) {
    const s = statusMeta[status] || statusMeta.todo;
    return `<span class="status-pill status-${s.cls}">${s.label}</span>`;
  }
  function priorityHTML(priority) {
    const p = priorityMeta[priority] || priorityMeta.medium;
    return `<span class="priority-pill priority-${p.cls}">${p.label}</span>`;
  }
  function avatarHTML(user, small = false) {
    if (!user) return '<span class="avatar avatar-muted">؟</span>';
    return `<span class="avatar ${small ? 'avatar-xs' : ''}" title="${escapeHTML(user.name)}">${escapeHTML(user.name.trim().slice(0, 1))}</span>`;
  }
  function emptyState(title, description, actionLabel = '', actionAttr = '') {
    return `<div class="empty-state"><span class="empty-mark"><i data-lucide="inbox"></i></span><strong>${escapeHTML(title)}</strong><p>${escapeHTML(description)}</p>${actionLabel ? `<button class="secondary-button" ${actionAttr}>${escapeHTML(actionLabel)}</button>` : ''}</div>`;
  }
  function searchedTasks(list) {
    const query = searchTerm.trim().toLocaleLowerCase('fa');
    if (!query) return [...list];
    return list.filter((t) => {
      const a = userById(t.assigneeId)?.name || '';
      const p = projectById(t.projectId)?.name || '';
      const team = teamById(t.teamId)?.name || '';
      return [t.title, t.description, a, p, team].join(' ').toLocaleLowerCase('fa').includes(query);
    });
  }
  function renderDashboard() {
    const tasks = data.tasks;
    const total = tasks.length;
    const done = tasks.filter((t) => t.status === 'done').length;
    const progress = tasks.filter((t) => t.status === 'in-progress').length;
    const late = tasks.filter(overdue).length;
    const pct = total ? Math.round(done / total * 100) : 0;
    $('statTotal').textContent = fa(total);
    $('statProgress').textContent = fa(progress);
    $('statDone').textContent = fa(done);
    $('statOverdue').textContent = fa(late);
    $('progressPercent').textContent = `${fa(pct)}٪`;
    $('progressDoneLabel').textContent = `${fa(done)} کار`;
    $('progressOpenLabel').textContent = `${fa(total - done)} کار`;
    $('progressRing').style.setProperty('--progress', `${pct}%`);
    const openTasks = tasks.filter((t) => t.status !== 'done').sort((a, b) => (a.dueDate || '9999').localeCompare(b.dueDate || '9999')).slice(0, 5);
    $('upcomingTasks').innerHTML = openTasks.length ? openTasks.map((t) => {
      const user = userById(t.assigneeId);
      return `<button class="task-row" data-open-task="${escapeHTML(t.id)}"><span class="task-row-main"><span class="task-row-title">${escapeHTML(t.title)}</span><span class="task-row-meta">${escapeHTML(t.projectName || projectById(t.projectId)?.name || 'بدون پروژه')} · ${escapeHTML(user?.name || 'بدون مسئول')}</span></span><span class="task-due ${overdue(t) ? 'late' : ''}">${formatDate(t.dueDate)}</span><span class="task-row-status">${statusHTML(t.status)}</span></button>`;
    }).join('') : emptyState('هنوز کاری ثبت نشده', 'اولین کار را بسازید تا جریان پیگیری در اینجا شکل بگیرد.', 'ثبت اولین کار', 'data-create-task');
    const teamUsers = data.users.slice().sort((a, b) => (b.open_tasks || 0) - (a.open_tasks || 0)).slice(0, 5);
    $('teamLoad').innerHTML = teamUsers.length ? teamUsers.map((u) => {
      const max = Math.max(1, ...teamUsers.map((x) => Number(x.open_tasks || 0)));
      const width = Math.round(Number(u.open_tasks || 0) / max * 100);
      return `<div class="team-load-item">${avatarHTML(u, true)}<div class="team-load-copy"><strong>${escapeHTML(u.name)}</strong><span class="load-track"><i style="width:${width}%"></i></span></div><b>${fa(u.open_tasks || 0)}</b></div>`;
    }).join('') : emptyState('هنوز عضوی وجود ندارد', 'اعضای تیم را از صفحه اعضا دعوت کنید.');
    renderActivityList($('recentActivity'), data.activity.slice(0, 5));
  }
  function taskTableRows(list, includeAssignee) {
    if (!list.length) return `<tr><td colspan="${includeAssignee ? 7 : 6}">${emptyState('کاری پیدا نشد', 'با تغییر فیلترها یا ساخت یک کار جدید ادامه دهید.', 'ثبت کار جدید', 'data-create-task')}</td></tr>`;
    return list.map((task) => {
      const common = `<td><div class="table-task-name"><button class="task-check ${task.status === 'done' ? 'checked' : ''}" data-toggle-task="${escapeHTML(task.id)}" title="تغییر وضعیت">${task.status === 'done' ? '<i data-lucide="check"></i>' : ''}</button><button class="table-title-button" data-open-task="${escapeHTML(task.id)}">${escapeHTML(task.title)}</button></div></td>`;
      if (!includeAssignee) return `<tr>${common}<td>${escapeHTML(task.projectName || 'بدون پروژه')}</td><td>${priorityHTML(task.priority)}</td><td class="${overdue(task) ? 'task-due late' : 'task-due'}">${formatDate(task.dueDate)}</td><td>${statusHTML(task.status)}</td><td><button class="row-more" data-open-task="${escapeHTML(task.id)}" aria-label="جزئیات"><i data-lucide="arrow-up-left"></i></button></td></tr>`;
      return `<tr>${common}<td><span class="person-cell">${avatarHTML(userById(task.assigneeId), true)}${escapeHTML(task.assigneeName || 'بدون مسئول')}</span></td><td>${escapeHTML(task.teamName || 'بدون تیم')}</td><td>${priorityHTML(task.priority)}</td><td class="${overdue(task) ? 'task-due late' : 'task-due'}">${formatDate(task.dueDate)}</td><td>${statusHTML(task.status)}</td><td><button class="row-more" data-open-task="${escapeHTML(task.id)}" aria-label="جزئیات"><i data-lucide="arrow-up-left"></i></button></td></tr>`;
    }).join('');
  }
  function renderMyTasks() {
    let list = searchedTasks(data.tasks.filter((t) => t.assigneeId === me.id));
    if (currentFilter.my === 'open') list = list.filter((t) => t.status !== 'done');
    if (currentFilter.my === 'done') list = list.filter((t) => t.status === 'done');
    const sort = $('mySort').value;
    if (sort === 'due') list.sort((a, b) => (a.dueDate || '9999').localeCompare(b.dueDate || '9999'));
    if (sort === 'priority') list.sort((a, b) => ({ urgent: 0, high: 1, medium: 2, low: 3 }[a.priority] - { urgent: 0, high: 1, medium: 2, low: 3 }[b.priority]));
    if (sort === 'newest') list.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    $('myTasksTable').innerHTML = taskTableRows(list, false);
  }
  function renderAllTasks() {
    let list = searchedTasks(data.tasks);
    const filter = currentFilter.all;
    if (filter !== 'all') list = list.filter((t) => t.status === filter);
    const teamId = $('teamFilter').value;
    const projectId = $('projectFilter').value;
    if (teamId !== 'all') list = list.filter((t) => t.teamId === teamId);
    if (projectId !== 'all') list = list.filter((t) => t.projectId === projectId);
    list.sort((a, b) => (a.dueDate || '9999').localeCompare(b.dueDate || '9999'));
    $('allTasksTable').innerHTML = taskTableRows(list, true);
  }
  function renderBoard() {
    const tasks = searchedTasks(data.tasks);
    $('kanbanBoard').innerHTML = boardColumns.map((col) => {
      const cards = tasks.filter((t) => t.status === col.id);
      return `<section class="kanban-column" data-drop-status="${col.id}"><div class="kanban-head"><strong>${col.label}</strong><span>${fa(cards.length)}</span></div><div class="kanban-cards">${cards.length ? cards.map((task) => `<article class="kanban-card" draggable="true" data-drag-task="${escapeHTML(task.id)}" data-open-task="${escapeHTML(task.id)}"><div class="kanban-card-tags">${priorityHTML(task.priority)}${overdue(task) ? '<span class="late-mark">دیرکرد</span>' : ''}</div><h3>${escapeHTML(task.title)}</h3><p>${escapeHTML(task.projectName || 'بدون پروژه')}</p><div class="kanban-card-foot"><span>${formatDate(task.dueDate)}</span>${avatarHTML(userById(task.assigneeId), true)}</div></article>`).join('') : '<div class="kanban-empty">کار دیگری در این ستون نیست.</div>'}</div></section>`;
    }).join('');
  }
  function renderCalendar() {
    const y = calendarDate.getFullYear();
    const m = calendarDate.getMonth();
    $('calendarMonth').textContent = calendarDate.toLocaleDateString('fa-IR', { month: 'long', year: 'numeric' });
    const first = new Date(y, m, 1);
    const startOffset = (first.getDay() + 1) % 7;
    const days = new Date(y, m + 1, 0).getDate();
    const previousDays = new Date(y, m, 0).getDate();
    const weekdays = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه'];
    let html = weekdays.map((day) => `<div class="calendar-cell calendar-weekday">${day}</div>`).join('');
    for (let i = 0; i < 42; i += 1) {
      let day, d, muted = false;
      if (i < startOffset) { day = previousDays - startOffset + i + 1; d = new Date(y, m - 1, day); muted = true; }
      else if (i >= startOffset + days) { day = i - startOffset - days + 1; d = new Date(y, m + 1, day); muted = true; }
      else { day = i - startOffset + 1; d = new Date(y, m, day); }
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const events = data.tasks.filter((t) => t.dueDate === iso).slice(0, 3);
      const today = iso === isoToday();
      html += `<div class="calendar-cell ${muted ? 'muted' : ''} ${today ? 'today' : ''}"><span class="calendar-day-number">${fa(day)}</span>${events.map((t) => `<button class="calendar-event ${t.status === 'done' ? 'green' : t.priority === 'urgent' ? 'urgent' : ''}" data-open-task="${escapeHTML(t.id)}">${escapeHTML(t.title)}</button>`).join('')}</div>`;
    }
    $('calendarGrid').innerHTML = html;
  }
  function renderProjects() {
    $('projectGrid').innerHTML = data.projects.length ? data.projects.map((project) => {
      const tasks = data.tasks.filter((t) => t.projectId === project.id);
      const done = tasks.filter((t) => t.status === 'done').length;
      const rate = tasks.length ? Math.round(done / tasks.length * 100) : 0;
      const tone = ['rust', 'green', 'blue', 'gold'].includes(project.color) ? project.color : 'rust';
      return `<article class="project-card"><div class="project-card-top"><span class="project-mark project-${tone}"><i data-lucide="folder-kanban"></i></span><button class="icon-button subtle" data-project-tasks="${escapeHTML(project.id)}" aria-label="کارهای پروژه"><i data-lucide="arrow-up-left"></i></button></div><h3>${escapeHTML(project.name)}</h3><p>${escapeHTML(project.description || 'توضیحی برای این پروژه ثبت نشده است.')}</p><div class="project-progress"><div class="project-progress-label"><span>پیشرفت بر اساس کارها</span><b>${fa(rate)}٪</b></div><div class="project-progress-track"><span style="width:${rate}%"></span></div></div><div class="project-card-foot"><span>${fa(tasks.length)} کار · ${fa(done)} تکمیل‌شده</span><span class="project-actions"><button class="text-button" data-edit-project="${escapeHTML(project.id)}">ویرایش</button>${isAdmin() ? `<button class="text-button danger-text" data-delete-project="${escapeHTML(project.id)}">حذف</button>` : ''}</span></div></article>`;
    }).join('') : emptyState('پروژه‌ای ساخته نشده', 'برای دسته‌بندی کارهای مرتبط، اولین پروژه را تعریف کنید.', 'ساخت پروژه', 'data-new-project');
  }
  function renderTeam() {
    $('teamGrid').innerHTML = data.users.length ? data.users.map((user) => `<article class="team-card">${avatarHTML(user)}<div class="team-info"><strong>${escapeHTML(user.name)}</strong><small>${escapeHTML(user.email)}</small></div><span class="role-pill role-${escapeHTML(user.role)}">${roleNames[user.role] || 'عضو'}</span><div class="team-card-count">${fa(user.open_tasks || 0)}<small>کار باز</small></div></article>`).join('') : emptyState('عضوی وجود ندارد', 'پس از دعوت همکاران، اعضای فضای کار در اینجا دیده می‌شوند.');
    $('teamGroups').innerHTML = data.teams.length ? data.teams.map((team) => {
      const teamTasks = data.tasks.filter((t) => t.teamId === team.id);
      const assignedIds = [...new Set(teamTasks.map((t) => t.assigneeId).filter(Boolean))];
      return `<div class="team-group-row"><span class="team-group-mark"><i data-lucide="users-round"></i></span><div><strong>${escapeHTML(team.name)}</strong><small>${escapeHTML(team.description || 'بدون توضیحات')}</small></div><b>${fa(teamTasks.length)} کار</b><span class="team-group-members">${assignedIds.length ? `${fa(assignedIds.length)} مسئول در کارها` : 'هنوز کاری واگذار نشده'}</span></div>`;
    }).join('') : emptyState('تیمی ایجاد نشده', 'یک تیم برای گروه‌بندی کارها بسازید.');
    $('invitationList').innerHTML = isAdmin() ? (data.invitations.length ? data.invitations.map((inv) => `<div class="invitation-row"><span class="invite-symbol"><i data-lucide="mail"></i></span><div><strong>${escapeHTML(inv.email)}</strong><small>${roleNames[inv.role] || 'عضو'} · اعتبار تا ${formatDate(inv.expires_at?.slice(0, 10))}</small></div><button class="text-button danger-text" data-revoke-invite="${escapeHTML(inv.id)}">لغو</button></div>`).join('') : '<p class="muted-copy">دعوت فعالی در انتظار پاسخ نیست.</p>') : '';
  }
  function renderActivityList(target, activities) {
    if (!activities.length) {
      target.innerHTML = '<div class="empty-inline"><i data-lucide="clock-3"></i><span>هنوز فعالیتی ثبت نشده است.</span></div>';
      return;
    }
    target.innerHTML = activities.map((entry) => `<div class="activity-item"><span class="activity-symbol"><i data-lucide="${entry.entity_type === 'task' ? (entry.action === 'created' ? 'plus' : entry.action === 'commented' ? 'message-circle' : entry.action === 'deleted' ? 'trash-2' : 'refresh-cw') : entry.entity_type === 'member' ? 'user-plus' : entry.entity_type === 'project' ? 'folder-kanban' : 'activity'}"></i></span><div class="activity-copy"><strong>${escapeHTML(entry.user_name || 'عضو سابق')}</strong><span>${escapeHTML(entry.message)}</span><small>${formatDateTime(entry.created_at)}</small></div></div>`).join('');
  }
  function renderCurrentView() {
    if (activeView === 'my-tasks') renderMyTasks();
    if (activeView === 'all-tasks') renderAllTasks();
    if (activeView === 'board') renderBoard();
    if (activeView === 'calendar') renderCalendar();
    if (activeView === 'projects') renderProjects();
    if (activeView === 'team') renderTeam();
    if (activeView === 'activity') renderActivityList($('fullActivity'), data.activity);
    refreshIcons();
  }
  function renderAll() {
    renderDashboard();
    renderCurrentView();
    $('myTaskCount').textContent = fa(data.tasks.filter((t) => t.assigneeId === me.id && t.status !== 'done').length);
    refreshIcons();
  }
  function navigate(view) {
    if (!viewNames[view]) return;
    activeView = view;
    document.querySelectorAll('.view').forEach((el) => el.classList.toggle('active', el.dataset.viewSection === view));
    document.querySelectorAll('.nav-item[data-view]').forEach((el) => el.classList.toggle('active', el.dataset.view === view));
    $('breadcrumbCurrent').textContent = viewNames[view];
    $('sidebar').classList.remove('open');
    renderCurrentView();
  }
  function showModal(id) {
    const node = $(id);
    node.classList.add('open');
    node.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }
  function closeModals() {
    document.querySelectorAll('.modal-backdrop.open').forEach((node) => {
      node.classList.remove('open');
      node.setAttribute('aria-hidden', 'true');
    });
    document.body.classList.remove('modal-open');
  }
  function resetTaskForm() {
    $('taskForm').reset();
    $('taskId').value = '';
    $('taskModalTitle').textContent = 'کار جدید';
    $('saveTaskLabel').textContent = 'ثبت کار';
    $('taskDue').value = '';
    populateFiltersAndForm();
    $('taskAssignee').value = me.id;
  }
  function openTaskForm(task = null) {
    resetTaskForm();
    if (task) {
      $('taskId').value = task.id;
      $('taskTitle').value = task.title;
      $('taskDescription').value = task.description || '';
      $('taskAssignee').value = task.assigneeId || '';
      $('taskTeam').value = task.teamId || '';
      $('taskProject').value = task.projectId || '';
      $('taskStatus').value = task.status;
      $('taskPriority').value = task.priority;
      $('taskDue').value = task.dueDate || '';
      $('taskEstimate').value = task.estimate ?? '';
      $('taskModalTitle').textContent = 'ویرایش کار';
      $('saveTaskLabel').textContent = 'ذخیره تغییرات';
    }
    closeModals();
    showModal('taskModal');
    $('taskTitle').focus();
  }
  function taskPayload() {
    return {
      title: $('taskTitle').value.trim(), description: $('taskDescription').value.trim(),
      assignee_id: $('taskAssignee').value || null, team_id: $('taskTeam').value || null,
      project_id: $('taskProject').value || null, status: $('taskStatus').value,
      priority: $('taskPriority').value, due_date: $('taskDue').value || null,
      estimate: $('taskEstimate').value ? Number($('taskEstimate').value) : null
    };
  }
  async function reloadData() {
    const boot = await api('/api/bootstrap');
    me = boot.me;
    data = { tasks: boot.tasks || [], users: boot.users || [], teams: boot.teams || [], projects: boot.projects || [], activity: boot.activity || [], invitations: boot.invitations || [] };
    renderIdentity();
    populateFiltersAndForm();
    renderAll();
  }
  async function openTaskDetail(taskId) {
    const task = data.tasks.find((t) => t.id === taskId);
    if (!task) return;
    selectedTaskId = taskId;
    $('detailTitle').textContent = task.title;
    $('deleteTaskButton').classList.toggle('hidden', !isAdmin() && task.createdBy !== me.id);
    $('detailBody').innerHTML = `<div class="detail-meta">${statusHTML(task.status)}${priorityHTML(task.priority)}${overdue(task) ? '<span class="late-mark">از موعد گذشته</span>' : ''}</div><p class="detail-description">${escapeHTML(task.description || 'برای این کار توضیحی ثبت نشده است.')}</p><div class="detail-info-grid"><div class="detail-info"><span>مسئول</span><strong>${escapeHTML(task.assigneeName || 'بدون مسئول')}</strong></div><div class="detail-info"><span>تیم</span><strong>${escapeHTML(task.teamName || 'بدون تیم')}</strong></div><div class="detail-info"><span>پروژه</span><strong>${escapeHTML(task.projectName || 'بدون پروژه')}</strong></div><div class="detail-info"><span>موعد</span><strong>${fullDate(task.dueDate)}</strong></div><div class="detail-info"><span>برآورد زمان</span><strong>${task.estimate ? `${fa(task.estimate)} ساعت` : 'ثبت نشده'}</strong></div><div class="detail-info"><span>آخرین تغییر</span><strong>${formatDateTime(task.updatedAt)}</strong></div></div>`;
    $('commentList').innerHTML = '<p class="muted-copy">در حال دریافت یادداشت‌ها...</p>';
    showModal('detailModal');
    refreshIcons();
    try {
      const comments = await api(`/api/tasks/${encodeURIComponent(taskId)}/comments`);
      if (selectedTaskId !== taskId) return;
      $('commentList').innerHTML = comments.length ? comments.map((c) => `<div class="comment-item"><span class="avatar avatar-xs">${escapeHTML((c.user_name || '؟').slice(0, 1))}</span><div><strong>${escapeHTML(c.user_name)}</strong><p>${escapeHTML(c.body)}</p><small>${formatDateTime(c.created_at)}</small></div></div>`).join('') : '<p class="muted-copy">هنوز یادداشتی برای این کار ثبت نشده است.</p>';
    } catch (error) {
      $('commentList').innerHTML = `<p class="muted-copy">${escapeHTML(error.message)}</p>`;
    }
  }
  async function saveTaskStatus(task, status) {
    const payload = {
      title: task.title, description: task.description || '', status, priority: task.priority,
      assignee_id: task.assigneeId, team_id: task.teamId, project_id: task.projectId,
      due_date: task.dueDate, estimate: task.estimate
    };
    await api(`/api/tasks/${encodeURIComponent(task.id)}`, { method: 'PATCH', body: payload });
    await reloadData();
    toast('وضعیت کار به‌روزرسانی شد.');
  }

  function startTour() {
    selectedTourStep = 0;
    $('tourBackdrop').classList.remove('hidden');
    renderTourStep();
  }
  function renderTourStep() {
    const step = tourSteps[selectedTourStep];
    navigate(step.view);
    document.querySelectorAll('.tour-highlight').forEach((el) => el.classList.remove('tour-highlight'));
    const target = document.querySelector(step.target);
    if (target) target.classList.add('tour-highlight');
    $('tourStepLabel').textContent = `گام ${fa(selectedTourStep + 1)} از ${fa(tourSteps.length)}`;
    $('tourTitle').textContent = step.title;
    $('tourText').textContent = step.text;
    $('tourProgress').innerHTML = tourSteps.map((_, i) => `<span class="${i <= selectedTourStep ? 'filled' : ''}"></span>`).join('');
    $('tourPrev').disabled = selectedTourStep === 0;
    $('tourNext').innerHTML = selectedTourStep === tourSteps.length - 1 ? 'پایان راهنما <i data-lucide="check"></i>' : 'بعدی <i data-lucide="arrow-left"></i>';
    refreshIcons();
  }
  async function finishTour() {
    $('tourBackdrop').classList.add('hidden');
    document.querySelectorAll('.tour-highlight').forEach((el) => el.classList.remove('tour-highlight'));
    try { await api('/api/me/onboarding', { method: 'POST', body: { completed: true } }); me.onboardingCompleted = true; }
    catch (error) { toast(error.message, 'alert-circle'); }
  }

  async function handleRegister(event) {
    event.preventDefault();
    clearAuthError();
    const button = $('registerForm').querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/auth/register', { method: 'POST', body: {
        name: $('registerName').value.trim(), email: $('registerEmail').value.trim(), password: $('registerPassword').value,
        workspace_name: $('workspaceName').value.trim(), invite_code: inviteCode || null
      }});
      inviteCode = '';
      history.replaceState({}, '', location.pathname);
      await hydrate();
      toast('حساب شما با موفقیت ساخته شد.');
    } catch (error) { showAuthError(error.message); }
    finally { button.disabled = false; }
  }
  async function handleLogin(event) {
    event.preventDefault();
    clearAuthError();
    const button = $('loginForm').querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api('/api/auth/login', { method: 'POST', body: { email: $('loginEmail').value.trim(), password: $('loginPassword').value }});
      await hydrate();
      toast('با موفقیت وارد شدید.');
    } catch (error) { showAuthError(error.message); }
    finally { button.disabled = false; }
  }
  async function logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (_) { /* session may already be gone */ }
    me = null;
    data = { tasks: [], users: [], teams: [], projects: [], activity: [], invitations: [] };
    closeModals();
    $('tourBackdrop').classList.add('hidden');
    showAuth();
    $('loginForm').reset();
    toast('از حساب خارج شدید.', 'log-out');
  }

  // Authentication and account forms
  $('loginForm').addEventListener('submit', handleLogin);
  $('registerForm').addEventListener('submit', handleRegister);
  document.querySelectorAll('[data-auth-tab]').forEach((el) => el.addEventListener('click', () => switchAuth(el.dataset.authTab)));
  document.querySelectorAll('[data-switch-auth]').forEach((el) => el.addEventListener('click', () => switchAuth(el.dataset.switchAuth)));
  $('logoutButton').addEventListener('click', logout);
  $('logoutSettings').addEventListener('click', logout);

  // Navigation and page-level controls
  document.querySelectorAll('.nav-item[data-view]').forEach((el) => el.addEventListener('click', () => navigate(el.dataset.view)));
  document.querySelectorAll('[data-go]').forEach((el) => el.addEventListener('click', () => navigate(el.dataset.go)));
  $('focusButton').addEventListener('click', () => navigate('my-tasks'));
  $('mobileMenu').addEventListener('click', () => $('sidebar').classList.toggle('open'));
  $('globalCreate').addEventListener('click', () => openTaskForm());
  $('createTaskOverview').addEventListener('click', () => openTaskForm());
  document.addEventListener('click', (event) => {
    const create = event.target.closest('[data-create-task]');
    if (create) openTaskForm();
    const newProject = event.target.closest('[data-new-project]');
    if (newProject) { editingProjectId = null; $('projectForm').reset(); showModal('projectModal'); }
    const open = event.target.closest('[data-open-task]');
    if (open) openTaskDetail(open.dataset.openTask);
    const toggle = event.target.closest('[data-toggle-task]');
    if (toggle) {
      event.stopPropagation();
      const task = data.tasks.find((t) => t.id === toggle.dataset.toggleTask);
      if (task) saveTaskStatus(task, task.status === 'done' ? 'todo' : 'done').catch((error) => toast(error.message, 'alert-circle'));
    }
    const projectTasks = event.target.closest('[data-project-tasks]');
    if (projectTasks) { $('projectFilter').value = projectTasks.dataset.projectTasks; navigate('all-tasks'); }
    const deleteProject = event.target.closest('[data-delete-project]');
    if (deleteProject && confirm('پروژه حذف شود؟ کارهای متصل به آن باقی می‌مانند و بدون پروژه خواهند شد.')) {
      api(`/api/projects/${encodeURIComponent(deleteProject.dataset.deleteProject)}`, { method: 'DELETE' }).then(reloadData).then(() => toast('پروژه حذف شد.', 'trash-2')).catch((error) => toast(error.message, 'alert-circle'));
    }
    const editProject = event.target.closest('[data-edit-project]');
    if (editProject) {
      const project = projectById(editProject.dataset.editProject);
      if (project) {
        editingProjectId = project.id;
        $('projectName').value = project.name;
        $('projectDescription').value = project.description || '';
        $('projectColor').value = project.color || 'rust';
        $('projectModal').querySelector('h2').textContent = 'ویرایش پروژه';
        $('projectModal').querySelector('button[type="submit"]').textContent = 'ذخیره پروژه';
        showModal('projectModal');
      }
    }
    const revoke = event.target.closest('[data-revoke-invite]');
    if (revoke && confirm('این دعوت‌نامه لغو شود؟')) api(`/api/invitations/${encodeURIComponent(revoke.dataset.revokeInvite)}`, { method: 'DELETE' }).then(reloadData).then(() => toast('دعوت‌نامه لغو شد.')).catch((error) => toast(error.message, 'alert-circle'));
  });
  $('globalSearch').addEventListener('input', (event) => {
    searchTerm = event.target.value;
    renderCurrentView();
  });
  $('globalSearch').addEventListener('keydown', (event) => { if (event.key === 'Escape') { event.target.value = ''; searchTerm = ''; renderCurrentView(); } });
  $('mySort').addEventListener('change', renderMyTasks);
  $('teamFilter').addEventListener('change', renderAllTasks);
  $('projectFilter').addEventListener('change', renderAllTasks);
  document.querySelectorAll('[data-filter-group]').forEach((group) => group.addEventListener('click', (event) => {
    const button = event.target.closest('[data-filter]');
    if (!button) return;
    const key = group.dataset.filterGroup;
    currentFilter[key] = button.dataset.filter;
    group.querySelectorAll('.filter-tab').forEach((tab) => tab.classList.toggle('active', tab === button));
    if (key === 'my') renderMyTasks(); else renderAllTasks();
  }));

  // Task create/update/detail and comments
  $('taskForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const id = $('taskId').value;
    const button = $('taskForm').querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await api(id ? `/api/tasks/${encodeURIComponent(id)}` : '/api/tasks', { method: id ? 'PATCH' : 'POST', body: taskPayload() });
      closeModals();
      await reloadData();
      toast(id ? 'تغییرات کار ذخیره شد.' : 'کار جدید ثبت شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
    finally { button.disabled = false; }
  });
  $('editTaskButton').addEventListener('click', () => {
    const task = data.tasks.find((t) => t.id === selectedTaskId);
    if (task) openTaskForm(task);
  });
  $('deleteTaskButton').addEventListener('click', async () => {
    if (!selectedTaskId || !confirm('این کار برای همه اعضای فضای کاری حذف شود؟')) return;
    try {
      await api(`/api/tasks/${encodeURIComponent(selectedTaskId)}`, { method: 'DELETE' });
      closeModals();
      await reloadData();
      toast('کار حذف شد.', 'trash-2');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });
  $('commentForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const body = $('commentBody').value.trim();
    if (!body || !selectedTaskId) return;
    try {
      await api(`/api/tasks/${encodeURIComponent(selectedTaskId)}/comments`, { method: 'POST', body: { body } });
      $('commentBody').value = '';
      await reloadData();
      await openTaskDetail(selectedTaskId);
      toast('یادداشت ثبت شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });

  // Kanban drag and drop
  document.addEventListener('dragstart', (event) => {
    const card = event.target.closest('[data-drag-task]');
    if (!card) return;
    draggedTaskId = card.dataset.dragTask;
    card.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedTaskId);
  });
  document.addEventListener('dragend', (event) => {
    const card = event.target.closest('[data-drag-task]');
    card?.classList.remove('dragging');
    document.querySelectorAll('.kanban-column.drag-over').forEach((el) => el.classList.remove('drag-over'));
  });
  document.addEventListener('dragover', (event) => {
    const column = event.target.closest('[data-drop-status]');
    if (!column) return;
    event.preventDefault();
    column.classList.add('drag-over');
  });
  document.addEventListener('dragleave', (event) => {
    const column = event.target.closest('[data-drop-status]');
    if (column && !column.contains(event.relatedTarget)) column.classList.remove('drag-over');
  });
  document.addEventListener('drop', async (event) => {
    const column = event.target.closest('[data-drop-status]');
    if (!column) return;
    event.preventDefault();
    column.classList.remove('drag-over');
    const taskId = event.dataTransfer.getData('text/plain') || draggedTaskId;
    const task = data.tasks.find((t) => t.id === taskId);
    const newStatus = column.dataset.dropStatus;
    if (!task || task.status === newStatus) return;
    try { await saveTaskStatus(task, newStatus); }
    catch (error) { toast(error.message, 'alert-circle'); }
  });

  // Calendar
  $('prevMonth').addEventListener('click', () => { calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() - 1, 1); renderCalendar(); });
  $('nextMonth').addEventListener('click', () => { calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 1); renderCalendar(); });

  // Projects, teams and invitations
  $('newProjectButton').addEventListener('click', () => {
    editingProjectId = null;
    $('projectForm').reset();
    $('projectModal').querySelector('h2').textContent = 'پروژه جدید';
    $('projectModal').querySelector('button[type="submit"]').textContent = 'ساخت پروژه';
    showModal('projectModal');
  });
  $('projectForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const payload = { name: $('projectName').value.trim(), description: $('projectDescription').value.trim(), color: $('projectColor').value };
    try {
      await api(editingProjectId ? `/api/projects/${encodeURIComponent(editingProjectId)}` : '/api/projects', { method: editingProjectId ? 'PATCH' : 'POST', body: payload });
      editingProjectId = null;
      closeModals();
      await reloadData();
      toast('پروژه ذخیره شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });
  $('inviteButton').addEventListener('click', () => { $('inviteForm').reset(); showModal('inviteModal'); });
  $('inviteForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const invite = await api('/api/invitations', { method: 'POST', body: { email: $('inviteEmail').value.trim(), role: $('inviteRole').value } });
      const link = `${location.origin}/?invite=${encodeURIComponent(invite.inviteCode)}`;
      $('inviteLinkValue').value = link;
      closeModals();
      showModal('inviteResultModal');
      await reloadData();
      toast('لینک دعوت ساخته شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });
  $('copyInviteLink').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText($('inviteLinkValue').value);
      toast('لینک دعوت کپی شد.', 'copy-check');
    } catch (_) {
      $('inviteLinkValue').select();
      document.execCommand('copy');
      toast('لینک دعوت کپی شد.', 'copy-check');
    }
  });
  $('newTeamButton').addEventListener('click', () => { $('teamForm').reset(); showModal('teamModal'); });
  $('teamForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await api('/api/teams', { method: 'POST', body: { name: $('teamName').value.trim(), description: $('teamDescription').value.trim() } });
      closeModals();
      await reloadData();
      toast('تیم جدید ساخته شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });

  // Profile and tour
  $('profileForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await api('/api/me', { method: 'PATCH', body: { name: $('profileNameInput').value.trim() } });
      await reloadData();
      toast('اطلاعات حساب به‌روزرسانی شد.');
    } catch (error) { toast(error.message, 'alert-circle'); }
  });
  $('helpButton').addEventListener('click', startTour);
  $('restartTourFromDocs').addEventListener('click', startTour);
  $('tourNext').addEventListener('click', () => {
    if (selectedTourStep >= tourSteps.length - 1) finishTour();
    else { selectedTourStep += 1; renderTourStep(); }
  });
  $('tourPrev').addEventListener('click', () => { if (selectedTourStep > 0) { selectedTourStep -= 1; renderTourStep(); } });
  $('tourSkip').addEventListener('click', finishTour);
  $('tourClose').addEventListener('click', finishTour);

  // Modal dismissal, keyboard shortcuts
  document.querySelectorAll('[data-close-modal]').forEach((el) => el.addEventListener('click', closeModals));
  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => backdrop.addEventListener('mousedown', (event) => { if (event.target === backdrop) closeModals(); }));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeModals();
      if (!$('tourBackdrop').classList.contains('hidden')) finishTour();
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      $('globalSearch').focus();
    }
    if (!event.ctrlKey && !event.metaKey && event.key.toLowerCase() === 'n' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !$('appShell').classList.contains('hidden')) {
      event.preventDefault();
      openTaskForm();
    }
    if (!event.ctrlKey && !event.metaKey && /^[1-5]$/.test(event.key) && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !$('appShell').classList.contains('hidden')) {
      const views = ['overview', 'my-tasks', 'all-tasks', 'board', 'calendar'];
      navigate(views[Number(event.key) - 1]);
    }
  });

  // Entry point
  switchAuth(inviteCode ? 'register' : 'login');
  checkSession();
  refreshIcons();
})();
