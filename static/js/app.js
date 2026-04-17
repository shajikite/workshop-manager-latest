let currentProgrammeId = null;
let allParticipants = [];

// Check auth on load
async function checkAuth() {
    const res = await fetch('/api/check-auth');
    const data = await res.json();
    if (data.admin) {
        document.getElementById('adminDashboard').style.display = 'block';
        document.getElementById('loginPanel').style.display = 'none';
        document.getElementById('userInfo').style.display = 'flex';
        document.getElementById('userNameDisplay').innerHTML = '<i class="fas fa-user-shield"></i> Admin';
        loadProgrammes();
        loadParticipants();
    } else if (data.participant) {
        document.getElementById('participantDashboard').style.display = 'block';
        document.getElementById('loginPanel').style.display = 'none';
        document.getElementById('userInfo').style.display = 'flex';
        document.getElementById('userNameDisplay').innerHTML = `<i class="fas fa-user"></i> ${data.participant_name}`;
        document.getElementById('welcomeName').innerText = data.participant_name;
        loadParticipantProgrammes();
    }
}

// Admin login
async function adminLogin() {
    const username = document.getElementById('adminUsername').value;
    const password = document.getElementById('adminPassword').value;
    const res = await fetch('/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (data.success) {
        location.reload();
    } else {
        alert('Login failed');
    }
}

// Participant login
async function participantLogin() {
    const pen_number = document.getElementById('participantPEN').value;
    const password = document.getElementById('participantPassword').value;
    const res = await fetch('/participant/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pen_number, password })
    });
    const data = await res.json();
    if (data.success) {
        location.reload();
    } else {
        alert('Login failed');
    }
}

// Logout
async function logout() {
    const isAdmin = document.getElementById('adminDashboard').style.display === 'block';
    window.location.href = isAdmin ? '/admin/logout' : '/participant/logout';
}

document.getElementById('logoutBtn')?.addEventListener('click', logout);
document.getElementById('adminLoginBtn')?.addEventListener('click', () => {
    document.getElementById('adminLoginCard').style.display = 'block';
    document.getElementById('participantLoginCard').style.display = 'block';
});
document.getElementById('participantLoginBtn')?.addEventListener('click', () => {
    document.getElementById('adminLoginCard').style.display = 'block';
    document.getElementById('participantLoginCard').style.display = 'block';
});

// Load programmes for admin
async function loadProgrammes() {
    const res = await fetch('/api/programmes');
    const programmes = await res.json();
    const container = document.getElementById('programmesList');
    container.innerHTML = programmes.map(p => `
        <div class="programme-card">
            <h3>${escapeHtml(p.name)}</h3>
            <p>${escapeHtml(p.description || '')}</p>
            <div class="dates">📅 ${p.from_date} to ${p.to_date} (${p.number_of_days} days)</div>
            <div class="card-actions">
                <button class="edit-btn" onclick="editProgramme(${p.id})"><i class="fas fa-edit"></i> Edit</button>
                <button class="delete-btn" onclick="deleteProgramme(${p.id})"><i class="fas fa-trash"></i> Delete</button>
                <button class="enroll-btn" onclick="openEnrollModal(${p.id}, '${escapeHtml(p.name)}')"><i class="fas fa-user-plus"></i> Enroll</button>
                <button class="view-btn" onclick="viewProgrammeParticipants(${p.id}, '${escapeHtml(p.name)}')"><i class="fas fa-eye"></i> View</button>
            </div>
        </div>
    `).join('');
}

// Programme CRUD
function openProgrammeModal(id = null) {
    if (id) {
        document.getElementById('programmeModalTitle').innerText = 'Edit Programme';
        fetch('/api/programmes')
            .then(res => res.json())
            .then(programmes => {
                const prog = programmes.find(p => p.id === id);
                if (prog) {
                    document.getElementById('programmeId').value = prog.id;
                    document.getElementById('progName').value = prog.name;
                    document.getElementById('progDesc').value = prog.description;
                    document.getElementById('progDays').value = prog.number_of_days;
                    document.getElementById('progFromDate').value = prog.from_date;
                    document.getElementById('progToDate').value = prog.to_date;
                }
            });
    } else {
        document.getElementById('programmeModalTitle').innerText = 'Create Programme';
        document.getElementById('programmeId').value = '';
        document.getElementById('progName').value = '';
        document.getElementById('progDesc').value = '';
        document.getElementById('progDays').value = '';
        document.getElementById('progFromDate').value = '';
        document.getElementById('progToDate').value = '';
    }
    document.getElementById('programmeModal').style.display = 'block';
}

async function saveProgramme() {
    const id = document.getElementById('programmeId').value;
    const data = {
        name: document.getElementById('progName').value,
        description: document.getElementById('progDesc').value,
        number_of_days: parseInt(document.getElementById('progDays').value),
        from_date: document.getElementById('progFromDate').value,
        to_date: document.getElementById('progToDate').value
    };
    
    const url = id ? `/api/programmes/${id}` : '/api/programmes';
    const method = id ? 'PUT' : 'POST';
    
    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok) {
        closeProgrammeModal();
        loadProgrammes();
    }
}

async function deleteProgramme(id) {
    if (confirm('Delete this programme?')) {
        await fetch(`/api/programmes/${id}`, { method: 'DELETE' });
        loadProgrammes();
    }
}

function closeProgrammeModal() {
    document.getElementById('programmeModal').style.display = 'none';
}

// Participant CRUD
async function loadParticipants() {
    const res = await fetch('/api/participants');
    const participants = await res.json();
    allParticipants = participants;
    const tbody = document.getElementById('participantsList');
    tbody.innerHTML = participants.map(p => `
        <tr>
            <td>${escapeHtml(p.pen_number)}</td>
            <td>${escapeHtml(p.name)}</td>
            <td>${escapeHtml(p.designation || '')}</td>
            <td>${escapeHtml(p.district || '')}</td>
            <td>
                <button class="edit-btn" onclick="editParticipant('${p.pen_number}')">Edit</button>
                <button class="delete-btn" onclick="deleteParticipant('${p.pen_number}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

function openParticipantModal(pen = null) {
    if (pen) {
        document.getElementById('participantModalTitle').innerText = 'Edit Participant';
        const p = allParticipants.find(p => p.pen_number === pen);
        if (p) {
            document.getElementById('participantPenOrig').value = p.pen_number;
            document.getElementById('participantPen').value = p.pen_number;
            document.getElementById('participantName').value = p.name;
            document.getElementById('participantDesignation').value = p.designation || '';
            document.getElementById('participantDistrict').value = p.district || '';
            document.getElementById('participantPass').value = '';
        }
    } else {
        document.getElementById('participantModalTitle').innerText = 'Add Participant';
        document.getElementById('participantPenOrig').value = '';
        document.getElementById('participantPen').value = '';
        document.getElementById('participantName').value = '';
        document.getElementById('participantDesignation').value = '';
        document.getElementById('participantDistrict').value = '';
        document.getElementById('participantPass').value = '';
    }
    document.getElementById('participantModal').style.display = 'block';
}

async function saveParticipant() {
    const penOrig = document.getElementById('participantPenOrig').value;
    const data = {
        pen_number: document.getElementById('participantPen').value,
        name: document.getElementById('participantName').value,
        designation: document.getElementById('participantDesignation').value,
        district: document.getElementById('participantDistrict').value,
        password: document.getElementById('participantPass').value
    };
    
    const url = penOrig ? `/api/participants/${penOrig}` : '/api/participants';
    const method = penOrig ? 'PUT' : 'POST';
    
    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (res.ok) {
        closeParticipantModal();
        loadParticipants();
    } else {
        const err = await res.json();
        alert(err.error || 'Error saving participant');
    }
}

async function deleteParticipant(pen) {
    if (confirm('Delete this participant?')) {
        await fetch(`/api/participants/${pen}`, { method: 'DELETE' });
        loadParticipants();
    }
}

function closeParticipantModal() {
    document.getElementById('participantModal').style.display = 'none';
}

// Enrollment with overlap checking
let currentEnrollProgrammeId = null;
let currentEnrollProgrammeName = '';

async function openEnrollModal(programmeId, programmeName) {
    currentEnrollProgrammeId = programmeId;
    currentEnrollProgrammeName = programmeName;
    document.getElementById('enrollProgName').innerText = programmeName;
    
    // Fetch all participants
    const participantsRes = await fetch('/api/participants');
    const allParticipantsList = await participantsRes.json();
    
    // Fetch currently enrolled participants for this programme
    const enrolledRes = await fetch(`/api/programmes/${programmeId}/participants`);
    const enrolled = await enrolledRes.json();
    const enrolledPens = new Set(enrolled.map(e => e.pen_number));
    
    // Build checklist
    const checklist = document.getElementById('participantsChecklist');
    checklist.innerHTML = allParticipantsList.map(p => `
        <div class="checklist-item" data-pen="${p.pen_number}" data-name="${escapeHtml(p.name)}">
            <label>
                <input type="checkbox" value="${p.pen_number}" ${enrolledPens.has(p.pen_number) ? 'checked disabled' : ''}>
                <strong>${escapeHtml(p.name)}</strong> (${escapeHtml(p.pen_number)}) - ${escapeHtml(p.designation || '')}
            </label>
        </div>
    `).join('');
    
    document.getElementById('enrollModal').style.display = 'block';
}

async function saveEnrollment() {
    const checkboxes = document.querySelectorAll('#participantsChecklist input[type="checkbox"]:checked:not([disabled])');
    const pen_numbers = Array.from(checkboxes).map(cb => cb.value);
    
    if (pen_numbers.length === 0) {
        alert('No participants selected');
        return;
    }
    
    // Check for overlaps
    const overlapRes = await fetch(`/api/programmes/${currentEnrollProgrammeId}/check-overlaps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pen_numbers })
    });
    const overlapData = await overlapRes.json();
    
    // Build warning message
    let warningMessage = '';
    let confirmedOverlaps = {};
    
    for (const [pen, overlaps] of Object.entries(overlapData.overlaps || {})) {
        const participantItem = document.querySelector(`.checklist-item[data-pen="${pen}"]`);
        const participantName = participantItem ? participantItem.dataset.name : pen;
        warningMessage += `\n\n📌 ${participantName} (${pen}):\n`;
        for (const [progName, dates] of Object.entries(overlaps)) {
            warningMessage += `   ⚠️ Already enrolled in "${progName}" on: ${dates.join(', ')}\n`;
            confirmedOverlaps[pen] = confirmedOverlaps[pen] || {};
            confirmedOverlaps[pen][progName] = dates;
        }
    }
    
    if (warningMessage) {
        const confirmEnroll = confirm(`⚠️ OVERLAPPING PROGRAMME DATES DETECTED!\n\n${warningMessage}\n\n❌ These dates will be DISABLED for attendance selection in this programme.\n\n✅ Do you still want to enroll these participants?`);
        if (!confirmEnroll) {
            return;
        }
    }
    
    // Proceed with enrollment
    const enrollRes = await fetch(`/api/programmes/${currentEnrollProgrammeId}/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            pen_numbers, 
            confirmed_overlaps: confirmedOverlaps 
        })
    });
    
    if (enrollRes.ok) {
        closeEnrollModal();
        alert('✅ Participants enrolled successfully!\n\nNote: Overlapping dates have been disabled for attendance selection.');
        if (currentViewProgrammeId) {
            viewProgrammeParticipants(currentViewProgrammeId, currentViewProgrammeName);
        }
    } else {
        alert('Error enrolling participants');
    }
}

function closeEnrollModal() {
    document.getElementById('enrollModal').style.display = 'none';
}

// View programme participants
let currentViewProgrammeId = null;
let currentViewProgrammeName = '';

async function viewProgrammeParticipants(programmeId, programmeName) {
    currentViewProgrammeId = programmeId;
    currentViewProgrammeName = programmeName;
    document.getElementById('ppProgName').innerText = `Participants: ${programmeName}`;
    
    const res = await fetch(`/api/programmes/${programmeId}/participants`);
    const participants = await res.json();
    
    const tbody = document.getElementById('programmeParticipantsList');
    tbody.innerHTML = participants.map(p => {
        const disabledDays = p.disabled_days ? JSON.parse(p.disabled_days) : [];
        return `
        <tr>
            <td>${escapeHtml(p.pen_number)}</td>
            <td>${escapeHtml(p.name)}</td>
            <td>${escapeHtml(p.designation || '')}</td>
            <td>${escapeHtml(p.district || '')}</td>
            <td>${p.willingness || 'Pending'}</td>
            <td>${p.attendance_days ? JSON.parse(p.attendance_days).join(', ') : '-'}</td>
            <td>${p.arrival_date || '-'} ${p.arrival_time || ''}</td>
            <td>${p.food_preference || '-'}</td>
            <td>${escapeHtml(p.remarks || '-')}</td>
            <td>
                ${disabledDays.length > 0 ? `<span title="Disabled days: ${disabledDays.join(', ')}" style="color: #e74c3c; cursor: help;">⚠️ ${disabledDays.length} days disabled</span><br>` : ''}
                <button class="delete-btn" onclick="removeParticipantFromProgramme(${programmeId}, '${p.pen_number}')">Remove</button>
            </td>
        </tr>
    `}).join('');
    
    document.getElementById('programmeParticipantsModal').style.display = 'block';
}

async function removeParticipantFromProgramme(programmeId, penNumber) {
    if (confirm('Remove this participant from the programme?')) {
        await fetch(`/api/programmes/${programmeId}/remove-participant/${penNumber}`, { method: 'DELETE' });
        viewProgrammeParticipants(programmeId, currentViewProgrammeName);
    }
}

function closeProgrammeParticipantsModal() {
    document.getElementById('programmeParticipantsModal').style.display = 'none';
}

function printParticipantList() {
    const printWindow = window.open('', '_blank');
    const tableHtml = document.getElementById('programmeParticipantsList').innerHTML;
    const programmeName = document.getElementById('ppProgName').innerText;
    printWindow.document.write(`
        <html><head><title>Participant List</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #f0f0f0; }
            h1 { color: #333; }
            @media print {
                body { margin: 0; padding: 20px; }
            }
        </style>
        </head><body>
        <h1>${programmeName}</h1>
        <table><thead><tr><th>PEN</th><th>Name</th><th>Designation</th><th>District</th>
        <th>Willingness</th><th>Attendance Days</th><th>Arrival</th><th>Food</th><th>Remarks</th></tr></thead>
        <tbody>${tableHtml}</tbody></table>
        <script>window.print();<\/script>
        </body></html>
    `);
}

function generateCateringReport() {
    if (currentViewProgrammeId) {
        window.open(`/api/programmes/${currentViewProgrammeId}/catering-report`, '_blank');
    }
}

function openDateWiseReport() {
    window.open('/api/date-wise-food-report', '_blank');
}

function openEnrollModalForCurrent() {
    openEnrollModal(currentViewProgrammeId, currentViewProgrammeName);
}

// Participant Dashboard
async function loadParticipantProgrammes() {
    const res = await fetch('/api/programmes');
    const programmes = await res.json();
    const container = document.getElementById('participantProgrammesList');
    
    container.innerHTML = programmes.map(p => {
        const disabledDays = p.disabled_days ? JSON.parse(p.disabled_days) : [];
        return `
        <div class="programme-card">
            ${p.is_enrolled ? '<div class="enrolled-badge"><i class="fas fa-check"></i> Enrolled</div>' : ''}
            ${p.willingness ? '<div class="response-badge"><i class="fas fa-reply"></i> Responded</div>' : ''}
            ${disabledDays.length > 0 ? '<div class="response-badge" style="background: #e74c3c;"><i class="fas fa-exclamation-triangle"></i> ' + disabledDays.length + ' days disabled</div>' : ''}
            <h3>${escapeHtml(p.name)}</h3>
            <p>${escapeHtml(p.description || '')}</p>
            <div class="dates">📅 ${p.from_date} to ${p.to_date} (${p.number_of_days} days)</div>
            ${p.is_enrolled ? `
                <div class="card-actions">
                    <button class="enroll-btn" onclick="openResponseModal(${p.id}, '${escapeHtml(p.name)}', ${p.number_of_days}, '${p.from_date}', ${JSON.stringify(p).replace(/"/g, '&quot;')})">
                        <i class="fas fa-edit"></i> ${p.willingness ? 'Update Response' : 'Confirm Participation'}
                    </button>
                </div>
            ` : '<div class="card-actions"><span style="color: #999;">Not enrolled yet</span></div>'}
        </div>
    `}).join('');
}

let currentResponseProgramme = null;

async function openResponseModal(programmeId, programmeName, numDays, fromDate, programmeData) {
    currentResponseProgramme = { id: programmeId, numDays, fromDate };
    document.getElementById('responseProgName').innerText = `Confirm Participation: ${programmeName}`;
    document.getElementById('responseProgId').value = programmeId;
    document.getElementById('responseWillingness').value = programmeData.willingness || '';
    document.getElementById('arrivalDate').value = programmeData.arrival_date || '';
    document.getElementById('arrivalTime').value = programmeData.arrival_time || '';
    document.getElementById('foodPreference').value = programmeData.food_preference || 'Vegetarian';
    document.getElementById('responseRemarks').value = programmeData.remarks || '';
    
    // Fetch disabled days for this participant in this programme
    const disabledRes = await fetch(`/api/participant/disabled-days/${programmeId}`);
    const disabledData = await disabledRes.json();
    const disabledDays = disabledData.disabled_days || [];
    
    // Generate attendance days checklist
    const days = [];
    const startDate = new Date(fromDate);
    for (let i = 0; i < numDays; i++) {
        const date = new Date(startDate);
        date.setDate(startDate.getDate() + i);
        days.push(date.toISOString().split('T')[0]);
    }
    
    const existingDays = programmeData.attendance_days ? JSON.parse(programmeData.attendance_days) : [];
    const checklistDiv = document.getElementById('attendanceDaysChecklist');
    
    if (disabledDays.length > 0) {
        checklistDiv.innerHTML += `<div style="background: #fff3cd; padding: 10px; margin-bottom: 15px; border-radius: 5px; border-left: 4px solid #ffc107;">
            <strong>⚠️ Notice:</strong> You are already enrolled in other programmes on the following dates, so they cannot be selected:<br>
            ${disabledDays.map(d => `📅 ${d}`).join(', ')}
        </div>`;
    }
    
    checklistDiv.innerHTML += days.map(day => {
        const isDisabled = disabledDays.includes(day);
        const isChecked = existingDays.includes(day);
        return `
            <div class="checklist-item" style="${isDisabled ? 'opacity: 0.5; background: #f5f5f5;' : ''}">
                <label>
                    <input type="checkbox" value="${day}" ${isChecked ? 'checked' : ''} ${isDisabled ? 'disabled' : ''}>
                    Day ${days.indexOf(day) + 1}: ${day}
                    ${isDisabled ? '<span style="color: #e74c3c; margin-left: 10px;"><i class="fas fa-ban"></i> (Already enrolled in another programme on this day)</span>' : ''}
                </label>
            </div>
        `;
    }).join('');
    
    // Show/hide attendance section based on willingness
    const attendanceSection = document.getElementById('attendanceSection');
    const willingnessSelect = document.getElementById('responseWillingness');
    
    const toggleAttendanceSection = () => {
        attendanceSection.style.display = willingnessSelect.value === 'Yes' ? 'block' : 'none';
    };
    
    willingnessSelect.removeEventListener('change', toggleAttendanceSection);
    willingnessSelect.addEventListener('change', toggleAttendanceSection);
    toggleAttendanceSection();
    
    document.getElementById('responseModal').style.display = 'block';
}

async function saveResponse() {
    const programmeId = document.getElementById('responseProgId').value;
    const willingness = document.getElementById('responseWillingness').value;
    
    if (!willingness) {
        alert('Please select willingness');
        return;
    }
    
    const attendanceDays = [];
    if (willingness === 'Yes') {
        const checkboxes = document.querySelectorAll('#attendanceDaysChecklist input[type="checkbox"]:checked:not([disabled])');
        checkboxes.forEach(cb => attendanceDays.push(cb.value));
    }
    
    const data = {
        programme_id: parseInt(programmeId),
        willingness,
        attendance_days: attendanceDays,
        arrival_date: document.getElementById('arrivalDate').value,
        arrival_time: document.getElementById('arrivalTime').value,
        food_preference: document.getElementById('foodPreference').value,
        remarks: document.getElementById('responseRemarks').value
    };
    
    const res = await fetch('/api/participant/response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    
    if (res.ok) {
        closeResponseModal();
        loadParticipantProgrammes();
        alert('Response saved successfully!');
    }
}

function closeResponseModal() {
    document.getElementById('responseModal').style.display = 'none';
    // Clear the checklist div for next time
    document.getElementById('attendanceDaysChecklist').innerHTML = '';
}

function showAdminTab(tab) {
    document.getElementById('programmesTab').style.display = tab === 'programmes' ? 'block' : 'none';
    document.getElementById('participantsTab').style.display = tab === 'participants' ? 'block' : 'none';
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    if (tab === 'programmes') loadProgrammes();
    if (tab === 'participants') loadParticipants();
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

// Search functionality for enrollment modal
document.getElementById('participantSearch')?.addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    const items = document.querySelectorAll('#participantsChecklist .checklist-item');
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? 'block' : 'none';
    });
});

// Initialize
checkAuth();
