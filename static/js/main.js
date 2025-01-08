let token = localStorage.getItem('jwt_token');

function checkAdminStatus() {
    const token = localStorage.getItem('jwt_token');
    
    // Token'ın geçerliliğini kontrol et
    if (token) {
        try {
            // Token'ı decode et ve süresini kontrol et
            const tokenData = JSON.parse(atob(token.split('.')[1]));
            const expTime = tokenData.exp * 1000; // Unix timestamp'i milisaniyeye çevir
            
            if (Date.now() >= expTime) {
                // Token süresi dolmuşsa çıkış yap
                handleLogout();
                return;
            }
            
            // Admin butonlarını göster
            document.querySelectorAll('.admin-only').forEach(el => {
                el.style.display = 'block';
            });
            
            // Admin menüsünü göster
            const adminMenu = document.querySelector('.admin-menu');
            if (adminMenu) {
                adminMenu.style.display = 'block';
            }
            
            // Giriş butonunu gizle
            const adminButtons = document.getElementById('adminButtons');
            if (adminButtons) {
                adminButtons.style.display = 'none';
            }
        } catch (error) {
            console.error('Token decode hatası:', error);
            handleLogout();
        }
    } else {
        // Token yoksa admin öğelerini gizle
        document.querySelectorAll('.admin-only').forEach(el => {
            el.style.display = 'none';
        });
        
        const adminMenu = document.querySelector('.admin-menu');
        if (adminMenu) {
            adminMenu.style.display = 'none';
        }
        
        const adminButtons = document.getElementById('adminButtons');
        if (adminButtons) {
            adminButtons.style.display = 'block';
        }
    }
}

// Sayfa yüklendiğinde ve URL değiştiğinde admin durumunu kontrol et
document.addEventListener('DOMContentLoaded', checkAdminStatus);
window.addEventListener('popstate', checkAdminStatus);

async function handleLogin(event) {
    event.preventDefault();
    
    const api_key = document.getElementById('api_key').value;
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ api_key })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('jwt_token', data.access_token);
            
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: 'Giriş başarılı.',
                showConfirmButton: false,
                timer: 1500
            }).then(() => {
                checkAdminStatus();
                // Sayfayı yenile
                window.location.reload();
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Hata!',
                text: 'Geçersiz API anahtarı!'
            });
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Giriş yapılırken bir hata oluştu!'
        });
    }
}

function handleLogout() {
    localStorage.removeItem('jwt_token');
    window.location.reload();
}

async function adminRequest(url, method, data = null) {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Bu işlem için admin girişi gerekli!'
        });
        return null;
    }
    
    try {
        const options = {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error('İşlem başarısız');
        }
        
        return await response.json();
    } catch (error) {
        console.error('İşlem hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'İşlem sırasında bir hata oluştu!'
        });
        return null;
    }
}

// Admin işlemleri için yardımcı fonksiyonlar
async function deletePlayer(id) {
    const result = await Swal.fire({
        title: 'Emin misiniz?',
        text: "Bu oyuncuyu silmek istediğinizden emin misiniz?",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Evet, sil!',
        cancelButtonText: 'İptal'
    });

    if (result.isConfirmed) {
        Swal.showLoading();
        const apiResult = await adminRequest(`/api/players/${id}`, 'DELETE');
        if (apiResult) {
            Swal.fire(
                'Silindi!',
                'Oyuncu başarıyla silindi.',
                'success'
            ).then(() => {
                window.location.reload();
            });
        }
    }
}

// Oyuncu düzenleme
async function editPlayer(id, event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    if (!requireAdmin()) return;
    
    try {
        const response = await fetch(`/api/players/${id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Oyuncu bilgileri alınamadı');
        }

        const player = await response.json();
        
        // Form alanlarını doldur
        document.getElementById('edit_player_id').value = player.id;
        document.getElementById('edit_name').value = player.name;
        document.getElementById('edit_position').value = player.position;
        
        // Statları güncelle ve değerlerini göster
        const stats = ['pace', 'shooting', 'passing', 'dribbling', 'defending', 'physical'];
        stats.forEach(stat => {
            const input = document.getElementById(`edit_${stat}`);
            input.value = player[stat];
            updateStatValue(input);
        });
        
        // Modal'ı göster
        const editModal = new bootstrap.Modal(document.getElementById('editPlayerModal'));
        editModal.show();
    } catch (error) {
        console.error('Oyuncu düzenleme hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Oyuncu bilgileri alınamadı!'
        });
    }
}

// Oyuncu düzenleme formunu dinle
document.addEventListener('DOMContentLoaded', function() {
    const editPlayerForm = document.getElementById('editPlayerForm');
    if (editPlayerForm) {
        editPlayerForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const id = document.getElementById('edit_player_id').value;
            const data = {
                name: document.getElementById('edit_name').value,
                position: document.getElementById('edit_position').value,
                pace: parseInt(document.getElementById('edit_pace').value),
                shooting: parseInt(document.getElementById('edit_shooting').value),
                passing: parseInt(document.getElementById('edit_passing').value),
                dribbling: parseInt(document.getElementById('edit_dribbling').value),
                defending: parseInt(document.getElementById('edit_defending').value),
                physical: parseInt(document.getElementById('edit_physical').value)
            };
            
            try {
                const response = await fetch(`/api/players/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    $('#editPlayerModal').modal('hide');
                    window.location.reload();
                } else {
                    alert('Oyuncu güncellenirken bir hata oluştu!');
                }
            } catch (error) {
                console.error('Güncelleme hatası:', error);
                alert('Oyuncu güncellenirken bir hata oluştu!');
            }
        });
    }
});

// Takım oyuncularını al
function getTeamPlayers(teamId) {
    const teamArea = document.getElementById(teamId);
    if (!teamArea) return [];
    
    return Array.from(teamArea.children).map(player => player.dataset.playerId);
}

// Yeni maç oluşturma
async function handleAddMatch(event) {
    event.preventDefault();
    if (!requireAdmin()) return;

    const dateInput = document.getElementById('date');
    const locationInput = document.getElementById('location');
    const totalCostInput = document.getElementById('total_cost');

    // Takımları kontrol et
    const teamA = getTeamPlayers('team-a');
    const teamB = getTeamPlayers('team-b');

    if (teamA.length === 0 || teamB.length === 0) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Her iki takımda da en az bir oyuncu olmalıdır!'
        });
        return;
    }

    // Tarihi doğru formata çevir
    const selectedDate = new Date(dateInput.value);
    const formattedDate = `${selectedDate.getDate()}/${selectedDate.getMonth() + 1}/${selectedDate.getFullYear()} ${selectedDate.getHours()}:${selectedDate.getMinutes()}`;

    const data = {
        date: formattedDate,
        location: locationInput.value,
        total_cost: parseFloat(totalCostInput.value),
        team_a: teamA,
        team_b: teamB
    };

    try {
        const response = await fetch('/api/matches', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: 'Maç başarıyla oluşturuldu.',
                showConfirmButton: false,
                timer: 1500
            }).then(() => {
                window.location.href = '/matches';
            });
        } else {
            throw new Error('Maç oluşturulamadı');
        }
    } catch (error) {
        console.error('Maç oluşturma hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Maç oluşturulurken bir hata oluştu!'
        });
    }
}

async function deleteMatch(id) {
    const result = await Swal.fire({
        title: 'Emin misiniz?',
        text: "Bu maçı silmek istediğinizden emin misiniz? Bu işlem geri alınamaz!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Evet, sil!',
        cancelButtonText: 'İptal'
    });

    if (result.isConfirmed) {
        try {
            const response = await fetch(`/api/matches/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (response.ok && data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Başarılı!',
                    text: data.message,
                    showConfirmButton: false,
                    timer: 1500
                }).then(() => {
                    window.location.href = '/matches';
                });
            } else {
                throw new Error(data.message || 'Silme işlemi başarısız');
            }
        } catch (error) {
            console.error('Maç silme hatası:', error);
            Swal.fire({
                icon: 'error',
                title: 'Hata!',
                text: 'Maç silinirken bir hata oluştu!'
            });
        }
    }
}

// Maç düzenleme
async function editMatch(id) {
    if (!requireAdmin()) return;
    
    try {
        const token = localStorage.getItem('jwt_token');
        const response = await fetch(`/api/matches/${id}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error('Maç bilgileri alınamadı');
        }

        const match = await response.json();
        
        // Modal'ı göster ve sonra form alanlarını doldur
        $('#editMatchModal').modal('show');
        
        // Modal tamamen açıldıktan sonra form alanlarını doldur
        $('#editMatchModal').on('shown.bs.modal', function () {
            // Form alanlarını doldur
            document.getElementById('edit_match_id').value = match.id;
            
            // Tarihi doğru formata çevir
            const matchDate = new Date(match.date);
            const formattedDate = matchDate.toISOString().slice(0, 16); // "YYYY-MM-DDThh:mm" formatı
            document.getElementById('edit_date').value = formattedDate;
            
            document.getElementById('edit_location').value = match.location;
            document.getElementById('edit_total_cost').value = match.total_cost;
            
            if (match.score_team_a !== null) {
                document.getElementById('edit_score_team_a').value = match.score_team_a;
            }
            if (match.score_team_b !== null) {
                document.getElementById('edit_score_team_b').value = match.score_team_b;
            }
        });
        
    } catch (error) {
        console.error('Maç düzenleme hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Maç bilgileri alınamadı!'
        });
    }
}

// Maç güncelleme
async function updateMatch(id, data) {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Bu işlem için admin girişi gerekli!'
        });
        return;
    }

    try {
        Swal.showLoading();
        const response = await fetch(`/api/matches/${id}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: 'Maç bilgileri güncellendi.',
                showConfirmButton: false,
                timer: 1500
            }).then(() => {
                window.location.reload();
            });
        } else {
            throw new Error('Güncelleme başarısız');
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Maç güncellenirken bir hata oluştu!'
        });
    }
}

// Düzenleme formunun gönderilmesi
document.addEventListener('DOMContentLoaded', function() {
    const editMatchForm = document.getElementById('editMatchForm');
    if (editMatchForm) {
        editMatchForm.addEventListener('submit', async function(event) {
            event.preventDefault();
            const id = document.getElementById('edit_match_id').value;
            const data = {
                date: document.getElementById('edit_date').value,
                location: document.getElementById('edit_location').value,
                total_cost: parseFloat(document.getElementById('edit_total_cost').value),
                score_team_a: document.getElementById('edit_score_team_a').value ? 
                    parseInt(document.getElementById('edit_score_team_a').value) : null,
                score_team_b: document.getElementById('edit_score_team_b').value ? 
                    parseInt(document.getElementById('edit_score_team_b').value) : null
            };
            
            try {
                const response = await fetch(`/api/matches/${id}`, {
                    method: 'PUT',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                if (response.ok) {
                    $('#editMatchModal').modal('hide');
                    window.location.reload();
                } else {
                    alert('Maç güncellenirken bir hata oluştu!');
                }
            } catch (error) {
                console.error('Güncelleme hatası:', error);
                alert('Maç güncellenirken bir hata oluştu!');
            }
        });
    }
});

function updateMatchTimer(matchId, matchDate) {
    const now = new Date();
    const diff = matchDate - now;
    
    if (diff <= 0) {
        $(`#timer-${matchId}`).fadeOut();
        return;
    }
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    $(`#timer-${matchId}`).html(`
        <i class="fas fa-clock"></i>
        ${days}g ${hours}s ${minutes}d
    `);
}

// Framer Motion animasyonları
const fadeIn = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5 }
};

// Sayfa yüklendiğinde animasyonları başlat
document.addEventListener('DOMContentLoaded', function() {
    const elements = document.querySelectorAll('.fade-in');
    elements.forEach((el, i) => {
        el.style.opacity = '0';
        setTimeout(() => {
            el.style.animation = 'fadeIn 0.5s ease forwards';
        }, i * 100);
    });
});

// Stat değerlerini güncelleme
function updateStatValue(input) {
    const value = input.value;
    const valueDisplay = document.getElementById(`${input.id}_value`);
    if (valueDisplay) {
        valueDisplay.textContent = value;
    }
}

// Oyuncu ekleme fonksiyonunu güncelle
async function handleAddPlayer(event) {
    event.preventDefault();
    const data = {
        name: document.getElementById('name').value,
        position: document.getElementById('position').value,
        pace: parseInt(document.getElementById('pace').value),
        shooting: parseInt(document.getElementById('shooting').value),
        passing: parseInt(document.getElementById('passing').value),
        dribbling: parseInt(document.getElementById('dribbling').value),
        defending: parseInt(document.getElementById('defending').value),
        physical: parseInt(document.getElementById('physical').value)
    };
    
    const result = await adminRequest('/api/players', 'POST', data);
    if (result) {
        window.location.reload();
    }
}

// Sürükle-bırak işlemleri için yeni bir fonksiyon
function initDragAndDrop() {
    const draggables = document.querySelectorAll('[draggable="true"]');
    const dropZones = document.querySelectorAll('.team-area');
    const playerPool = document.getElementById('available-players');

    draggables.forEach(draggable => {
        draggable.addEventListener('dragstart', () => {
            draggable.classList.add('dragging');
        });

        draggable.addEventListener('dragend', () => {
            draggable.classList.remove('dragging');
        });
    });

    [playerPool, ...dropZones].forEach(zone => {
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            if (zone.classList.contains('team-area')) {
                zone.classList.add('drag-over');
            }
        });

        zone.addEventListener('dragleave', () => {
            if (zone.classList.contains('team-area')) {
                zone.classList.remove('drag-over');
            }
        });

        zone.addEventListener('drop', e => {
            e.preventDefault();
            if (zone.classList.contains('team-area')) {
                zone.classList.remove('drag-over');
            }
            
            const draggable = document.querySelector('.dragging');
            if (!draggable) return;

            if (zone.classList.contains('team-area')) {
                const newTeam = zone.id === 'team-a' ? 'A' : 'B';
                draggable.dataset.team = newTeam;
            } else {
                delete draggable.dataset.team;
            }

            zone.appendChild(draggable);
        });
    });
}

// Sayfa yüklendiğinde sürükle-bırak işlemlerini başlat
document.addEventListener('DOMContentLoaded', initDragAndDrop);

// Ödeme durumu güncelleme
async function togglePaymentStatus(playerId, matchId) {
    if (!requireAdmin()) return;

    try {
        const response = await fetch(`/api/matches/${matchId}/players/${playerId}/payment`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const button = event.target.closest('button');
            
            // Buton rengini ve içeriğini güncelle
            button.classList.remove('btn-success', 'btn-danger');
            button.classList.add(data.has_paid ? 'btn-success' : 'btn-danger');
            
            const icon = button.querySelector('i');
            icon.classList.remove('fa-check', 'fa-times');
            icon.classList.add(data.has_paid ? 'fa-check' : 'fa-times');
            
            button.innerHTML = `
                <i class="fas fa-${data.has_paid ? 'check' : 'times'}"></i>
                ${data.has_paid ? 'Ödendi' : 'Ödenmedi'}
            `;
            
            // Başarı mesajı göster
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: 'Ödeme durumu güncellendi.',
                showConfirmButton: false,
                timer: 1500
            });
        } else {
            throw new Error('İşlem başarısız');
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Ödeme durumu güncellenirken bir hata oluştu!'
        });
    }
}

// Takım dengesi kontrolü
function updateTeamBalance() {
    const teamA = document.querySelector('#team-a');
    const teamB = document.querySelector('#team-b');
    
    const teamAPlayers = Array.from(teamA.querySelectorAll('.draggable-player'));
    const teamBPlayers = Array.from(teamB.querySelectorAll('.draggable-player'));
    
    const teamAOVR = calculateTeamOVR(teamAPlayers);
    const teamBOVR = calculateTeamOVR(teamBPlayers);
    
    // Takım güç dengesini göster
    updateTeamOVRDisplay(teamAOVR, teamBOVR);
}

function calculateTeamOVR(players) {
    if (players.length === 0) return 0;
    return Math.round(players.reduce((sum, player) => 
        sum + parseInt(player.dataset.ovr), 0) / players.length);
}

function updateTeamOVRDisplay(teamAOVR, teamBOVR) {
    const difference = Math.abs(teamAOVR - teamBOVR);
    const balanceIndicator = document.getElementById('team-balance');
    
    if (difference <= 3) {
        balanceIndicator.className = 'badge badge-success';
        balanceIndicator.textContent = 'Dengeli';
    } else if (difference <= 7) {
        balanceIndicator.className = 'badge badge-warning';
        balanceIndicator.textContent = 'Orta Dengeli';
    } else {
        balanceIndicator.className = 'badge badge-danger';
        balanceIndicator.textContent = 'Dengesiz';
    }
}

// Tarih seçici için Türkçe ayarları
$.fn.datetimepicker.dates['tr'] = {
    days: ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"],
    daysShort: ["Paz", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt"],
    daysMin: ["Pz", "Pt", "Sa", "Ça", "Pe", "Cu", "Ct"],
    months: ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"],
    monthsShort: ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
    today: "Bugün",
    clear: "Temizle",
    suffix: [],
    meridiem: ["öö", "ös"],
    format: "dd.mm.yyyy hh:ii",
    weekStart: 1
};

// Tarih seçiciyi başlat
$('.datetimepicker').datetimepicker({
    language: 'tr',
    autoclose: true,
    todayBtn: true,
    todayHighlight: true
});

// Tema değiştirme
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Tema ikonlarını güncelle
    const darkIcon = document.getElementById('darkModeIcon');
    const lightIcon = document.getElementById('lightModeIcon');
    
    if (newTheme === 'dark') {
        darkIcon.style.display = 'none';
        lightIcon.style.display = 'inline-block';
    } else {
        darkIcon.style.display = 'inline-block';
        lightIcon.style.display = 'none';
    }
}

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', function() {
    // Tema kontrolü
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const darkIcon = document.getElementById('darkModeIcon');
    const lightIcon = document.getElementById('lightModeIcon');
    
    if (savedTheme === 'dark') {
        darkIcon.style.display = 'none';
        lightIcon.style.display = 'inline-block';
    }
    
    // Tema toggle butonunu dinle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Admin durumunu kontrol et
    checkAdminStatus();
});

// Admin yetkisi kontrolü
function requireAdmin() {
    const token = localStorage.getItem('jwt_token');
    if (!token) {
        Swal.fire({
            icon: 'error',
            title: 'Yetkisiz Erişim',
            text: 'Bu sayfaya erişim için admin yetkisi gereklidir!',
            confirmButtonText: 'Giriş Yap'
        }).then(() => {
            window.location.href = '/login';
        });
        return false;
    }

    try {
        const tokenData = JSON.parse(atob(token.split('.')[1]));
        const expTime = tokenData.exp * 1000;
        
        if (Date.now() >= expTime) {
            Swal.fire({
                icon: 'error',
                title: 'Oturum Süresi Doldu',
                text: 'Lütfen tekrar giriş yapın!',
                confirmButtonText: 'Giriş Yap'
            }).then(() => {
                handleLogout();
                window.location.href = '/login';
            });
            return false;
        }
        return true;
    } catch (error) {
        console.error('Token decode hatası:', error);
        handleLogout();
        return false;
    }
}

// Sayfa yüklendiğinde admin kontrolü
document.addEventListener('DOMContentLoaded', function() {
    // Admin sayfalarında kontrol
    const adminPages = ['/new_match', '/edit_match', '/edit_player'];
    const currentPath = window.location.pathname;
    
    if (adminPages.some(page => currentPath.includes(page))) {
        if (!requireAdmin()) {
            return;
        }
    }
    
    checkAdminStatus();
    initDragAndDrop();
});

// Admin işlemleri için güvenlik kontrolü
async function secureAdminRequest(url, method, data = null) {
    if (!requireAdmin()) {
        return null;
    }

    const token = localStorage.getItem('jwt_token');
    try {
        const options = {
            method: method,
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, options);
        
        if (response.status === 401) {
            handleLogout();
            window.location.href = '/login';
            return null;
        }
        
        if (!response.ok) {
            throw new Error('İşlem başarısız');
        }
        
        return await response.json();
    } catch (error) {
        console.error('İşlem hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'İşlem sırasında bir hata oluştu!'
        });
        return null;
    }
}

// Her API isteğinde kullanılacak headers
function getAuthHeaders() {
    const token = localStorage.getItem('jwt_token');
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', function() {
    const token = localStorage.getItem('jwt_token');
    if (token) {
        // Token varsa her fetch isteğine ekle
        const originalFetch = window.fetch;
        window.fetch = function() {
            let [resource, config] = arguments;
            if(config === undefined) {
                config = {};
            }
            if(config.headers === undefined) {
                config.headers = {};
            }
            config.headers['Authorization'] = `Bearer ${token}`;
            return originalFetch(resource, config);
        };
    }
    
    checkAdminStatus();
    initDragAndDrop();
});

// Maç güncelleme işlemi
async function handleMatchUpdate(event, matchId) {
    event.preventDefault();
    if (!requireAdmin()) return;

    const form = event.target;
    const formData = new FormData(form);
    
    const data = {
        date: formData.get('date'),
        location: formData.get('location'),
        total_cost: parseFloat(formData.get('total_cost')),
        score_team_a: formData.get('score_team_a') ? parseInt(formData.get('score_team_a')) : null,
        score_team_b: formData.get('score_team_b') ? parseInt(formData.get('score_team_b')) : null
    };

    try {
        const response = await fetch(`/api/matches/${matchId}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: 'Maç bilgileri güncellendi.',
                showConfirmButton: false,
                timer: 1500
            });
        } else {
            throw new Error('Güncelleme başarısız');
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Maç güncellenirken bir hata oluştu!'
        });
    }
}

// Çeviri fonksiyonu
function getTranslation(key) {
    const lang = document.documentElement.lang || 'tr';
    return translations[lang][key] || key;
}

// Swal alert mesajlarında çeviri kullanımı
Swal.fire({
    icon: 'success',
    title: getTranslation('success'),
    text: getTranslation('match_updated'),
    showConfirmButton: false,
    timer: 1500
});

async function handleEditPlayer(event) {
    event.preventDefault();
    if (!requireAdmin()) return;

    const form = event.target;
    const playerId = form.querySelector('#edit_player_id').value;
    
    const data = {
        name: form.querySelector('#edit_name').value,
        position: form.querySelector('#edit_position').value,
        pace: parseInt(form.querySelector('#edit_pace').value),
        shooting: parseInt(form.querySelector('#edit_shooting').value),
        passing: parseInt(form.querySelector('#edit_passing').value),
        dribbling: parseInt(form.querySelector('#edit_dribbling').value),
        defending: parseInt(form.querySelector('#edit_defending').value),
        physical: parseInt(form.querySelector('#edit_physical').value)
    };

    try {
        const response = await fetch(`/api/players/${playerId}`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Modal'ı kapat
            const editModal = bootstrap.Modal.getInstance(document.getElementById('editPlayerModal'));
            editModal.hide();
            
            Swal.fire({
                icon: 'success',
                title: 'Başarılı!',
                text: result.message,
                showConfirmButton: false,
                timer: 1500
            }).then(() => {
                window.location.reload();
            });
        } else {
            throw new Error(result.message || 'Güncelleme başarısız');
        }
    } catch (error) {
        console.error('Oyuncu güncelleme hatası:', error);
        Swal.fire({
            icon: 'error',
            title: 'Hata!',
            text: 'Oyuncu güncellenirken bir hata oluştu!'
        });
    }
}

// Stat değerlerini güncelleme
function updateStatValue(input) {
    const value = input.value;
    const valueDisplay = document.getElementById(`${input.id}_value`);
    if (valueDisplay) {
        valueDisplay.textContent = value;
    }
}

// Tarih seçici ayarları
function initDatePicker(elementId) {
    const fp = flatpickr(elementId, {
        locale: 'tr',
        enableTime: true,
        dateFormat: "d.m.Y H:i",
        time_24hr: true,
        defaultDate: new Date(),
        minuteIncrement: 30,
        position: "auto",
        theme: "dark",
        disableMobile: "true",
        wrap: true
    });

    // Varsayılan tarihi ayarla
    const now = new Date();
    const roundedMinutes = Math.ceil(now.getMinutes() / 30) * 30;
    now.setMinutes(roundedMinutes);
    fp.setDate(now);

    return fp;
}

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', function() {
    const datePicker = document.getElementById('date');
    if (datePicker) {
        initDatePicker('#date');
    }
});

async function markAllAsPaid(matchId) {
    if (!requireAdmin()) return;

    try {
        const result = await Swal.fire({
            title: translate('confirm'),
            text: translate('confirm_mark_all_paid'),
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: translate('confirm'),
            cancelButtonText: translate('cancel')
        });

        if (result.isConfirmed) {
            const response = await fetch(`/api/matches/${matchId}/mark-all-paid`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`,
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (response.ok && data.success) {
                Swal.fire({
                    icon: 'success',
                    title: translate('success'),
                    text: data.message,
                    showConfirmButton: false,
                    timer: 1500
                }).then(() => {
                    window.location.reload();
                });
            } else {
                throw new Error(data.message || translate('error_occurred'));
            }
        }
    } catch (error) {
        console.error('Ödeme güncelleme hatası:', error);
        Swal.fire({
            icon: 'error',
            title: translate('error'),
            text: translate('payment_update_error')
        });
    }
}

// Konfeti efekti
function playConfetti() {
    confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#3498db', '#2ecc71', '#e74c3c', '#f1c40f', '#9b59b6']
    });
}

// Ses efekti
function playClickSound() {
    const audio = new Audio('/static/sounds/click.mp3');
    audio.volume = 0.2; // Ses seviyesi
    audio.play();
}

// Oyuncu kartına tıklama
document.addEventListener('DOMContentLoaded', function() {
    // Oyuncu kartları için
    const playerCards = document.querySelectorAll('.player-card');
    playerCards.forEach(card => {
        card.addEventListener('click', function(e) {
            playConfetti();
            playClickSound();
        });
    });

    // Maç kartları için
    const matchCards = document.querySelectorAll('.match-card');
    matchCards.forEach(card => {
        card.addEventListener('click', function(e) {
            playClickSound();
        });
    });
});

async function addComment(event) {
    event.preventDefault();
    const comment = document.getElementById('comment').value;
    const playerId = window.location.pathname.split('/').pop();
    
    try {
        const response = await fetch(`/api/comments/${playerId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ comment })
        });
        
        if (response.ok) {
            window.location.reload();
        }
    } catch (error) {
        console.error('Yorum eklenirken hata:', error);
    }
}

async function toggleLike() {
    const playerId = window.location.pathname.split('/').pop();
    const likeButton = document.querySelector('.btn-like');
    const likeCount = likeButton.nextElementSibling;
    
    try {
        const response = await fetch(`/api/likes/${playerId}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            likeButton.classList.toggle('liked');
            likeCount.textContent = result.likes_count;
            
            // Konfeti efekti
            if (likeButton.classList.contains('liked')) {
                confetti({
                    particleCount: 50,
                    spread: 30,
                    origin: { y: 0.8 }
                });
            }
        }
    } catch (error) {
        console.error('Beğeni işlemi sırasında hata:', error);
        Swal.fire({
            icon: 'error',
            title: translate('error'),
            text: translate('like_error')
        });
    }
}

async function editPlayerTC(playerId) {
    try {
        const response = await fetch(`/api/players/${playerId}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Oyuncu bilgileri alınamadı');
        }

        const player = await response.json();
        
        const { value: tc_no } = await Swal.fire({
            title: translate('edit_tc'),
            input: 'text',
            inputLabel: translate('tc_no'),
            inputValue: player.tc_no || '',
            inputAttributes: {
                maxlength: '11',
                pattern: '\\d{11}'
            },
            showCancelButton: true,
            confirmButtonText: translate('save'),
            cancelButtonText: translate('cancel'),
            inputValidator: (value) => {
                if (!value) {
                    return translate('tc_required');
                }
                if (!/^\d{11}$/.test(value)) {
                    return translate('tc_invalid');
                }
            }
        });

        if (tc_no) {
            const updateResponse = await fetch(`/api/players/${playerId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`
                },
                body: JSON.stringify({ tc_no })
            });

            if (!updateResponse.ok) {
                throw new Error(await updateResponse.text());
            }

            const result = await updateResponse.json();
            
            if (result.success) {
                await Swal.fire({
                    icon: 'success',
                    title: translate('success'),
                    text: translate('tc_updated'),
                    timer: 1500
                });
                window.location.reload();
            } else {
                throw new Error(result.message);
            }
        }
    } catch (error) {
        console.error('TC güncelleme hatası:', error);
        await Swal.fire({
            icon: 'error',
            title: translate('error'),
            text: error.message
        });
    }
}

async function toggleReaction(isLike) {
    if (!isLoggedIn && !isAdmin) {
        Swal.fire({
            title: translate('login_required'),
            text: translate('login_required_for_reaction'),
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: translate('login'),
            cancelButtonText: translate('cancel')
        }).then((result) => {
            if (result.isConfirmed) {
                window.location.href = '/player-login';
            }
        });
        return;
    }

    const playerId = window.location.pathname.split('/').pop();
    
    try {
        const response = await fetch(`/api/likes/${playerId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Admin token'ı varsa ekle
                ...(isAdmin && {'Authorization': `Bearer ${localStorage.getItem('jwt_token')}`})
            },
            body: JSON.stringify({ is_like: isLike })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Yüzdeleri güncelle
            const likePercent = result.like_percent;
            const dislikePercent = result.dislike_percent;
            
            // Progress bar'ı güncelle
            document.querySelector('.progress-bar').style.width = `${likePercent}%`;
            
            // Yüzde metinlerini güncelle
            document.querySelector('.like-btn span').textContent = `%${Math.round(likePercent)}`;
            document.querySelector('.dislike-btn span').textContent = `%${Math.round(dislikePercent)}`;
            
            // Aktif butonları güncelle
            document.querySelector('.like-btn').classList.toggle('active', isLike);
            document.querySelector('.dislike-btn').classList.toggle('active', !isLike);
            
            // Toplam reaksiyon sayısını güncelle
            document.querySelector('.text-muted').textContent = 
                `${result.total_reactions} ${translate('total_reactions')}`;
        } else {
            throw new Error(await response.text());
        }
    } catch (error) {
        console.error('Reaksiyon hatası:', error);
        Swal.fire({
            icon: 'error',
            title: translate('error'),
            text: translate('reaction_error')
        });
    }
} 

function handleAdminLogout() {
    // Admin token'ı sil
    localStorage.removeItem('jwt_token');
    document.cookie = 'jwt_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
    
    // Admin durumunu güncelle
    isAdmin = false;
    
    // Sayfayı ana sayfaya yönlendir
    window.location.href = '/';
} 

// Form işlemleri için güvenlik kontrolü ekleyelim
document.addEventListener('DOMContentLoaded', function() {
    // Form elementini seç
    const commentForm = document.getElementById('commentForm');
    
    if (commentForm) {  // Form varsa işlem yap
        commentForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Input elementini seç
            const commentInput = document.getElementById('commentText');
            
            // Input kontrolü
            if (!commentInput) {
                console.error('Yorum input elementi bulunamadı');
                return;
            }
            
            const commentText = commentInput.value;
            
            if (!commentText.trim()) {
                alert('Lütfen bir yorum yazın');
                return;
            }
            
            try {
                const response = await fetch(`/api/players/{{ player._id }}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({
                        text: commentText
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Yorum gönderilemedi');
                }

                const comment = await response.json();
                
                // Yeni yorumu listeye ekle
                const commentsList = document.getElementById('commentsList');
                if (commentsList) {
                    const commentHtml = `
                        <div class="comment-item">
                            <div class="comment-header">
                                <strong>${comment.commenter_name}</strong>
                                <small>${new Date(comment.created_at).toLocaleString('tr-TR', {
                                    timeZone: 'Europe/Istanbul'
                                })}</small>
                            </div>
                            <p>${comment.text}</p>
                        </div>
                    `;
                    commentsList.insertAdjacentHTML('afterbegin', commentHtml);
                }
                
                // Formu temizle
                commentInput.value = '';

            } catch (error) {
                console.error('Yorum hatası:', error);
                alert(error.message || 'Yorum gönderilemedi. Lütfen tekrar deneyin.');
            }
        });
    }
});

// TC güncelleme fonksiyonu
async function updateTC(playerId) {
    try {
        const newTC = prompt('Yeni TC kimlik numarasını girin:');
        if (!newTC) return;

        const response = await fetch(`/api/players/${playerId}/update-tc`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'include',  // Cookie'leri gönder
            body: JSON.stringify({
                tc_no: newTC
            })
        });

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 403) {
                alert('Bu işlem için admin yetkisi gereklidir!');
                window.location.href = '/admin-login';
                return;
            }
            throw new Error(data.error || 'TC güncellenemedi');
        }

        alert('TC kimlik numarası başarıyla güncellendi');
        location.reload();

    } catch (error) {
        console.error('TC güncelleme hatası:', error);
        alert(error.message || 'TC güncellenemedi. Lütfen tekrar deneyin.');
    }
}

// Reaksiyon güncelleme fonksiyonu
async function updateReactionCounts(likes, dislikes) {
    try {
        const response = await fetch(`/api/players/${playerId}/reactions/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'include',  // Cookie'leri gönder
            body: JSON.stringify({
                likes: likes,
                dislikes: dislikes
            })
        });

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 403) {
                alert('Bu işlem için admin yetkisi gereklidir!');
                window.location.href = '/admin-login';
                return;
            }
            throw new Error(data.error || 'Beğeni sayıları güncellenemedi');
        }

        // UI güncelleme
        document.getElementById('likes-count').textContent = data.likes;
        document.getElementById('dislikes-count').textContent = data.dislikes;

        // Yüzdeleri güncelle
        const total = data.likes + data.dislikes;
        const likePercent = total > 0 ? (data.likes / total * 100) : 0;
        const dislikePercent = total > 0 ? (data.dislikes / total * 100) : 0;

        document.getElementById('like-percent').textContent = `%${likePercent.toFixed(1)}`;
        document.getElementById('dislike-percent').textContent = `%${dislikePercent.toFixed(1)}`;

        // SVG path'leri güncelle
        document.querySelector('.circle-like').setAttribute('stroke-dasharray', `${likePercent}, 100`);
        document.querySelector('.circle-dislike').setAttribute('stroke-dasharray', `${dislikePercent}, 100`);
        document.querySelector('.circle-dislike').setAttribute('transform', `rotate(${likePercent * 3.6} 18 18)`);

    } catch (error) {
        console.error('Güncelleme hatası:', error);
        alert(error.message || 'Beğeni sayıları güncellenemedi. Lütfen tekrar deneyin.');
    }
} 

document.addEventListener('DOMContentLoaded', function() {
    // Form kontrolü
    const commentForm = document.getElementById('commentForm');
    if (commentForm) {
        commentForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const commentInput = document.getElementById('commentText');
            if (!commentInput) return;
            // ... form işlemleri
        });
    }

    // Sürükle-bırak kontrolü
    function initDragAndDrop() {
        const dragElements = document.querySelectorAll('.draggable');
        if (!dragElements || dragElements.length === 0) return;
        
        dragElements.forEach(element => {
            if (element) {
                element.addEventListener('dragstart', handleDragStart);
                // ... diğer sürükle-bırak işlemleri
            }
        });
    }

    // Tarih kontrolü
    function initDateHandling() {
        const dateElement = document.querySelector('.date-element');
        if (!dateElement || !dateElement.dates) return;
        // ... tarih işlemleri
    }

    // İşlevleri çağır
    initDragAndDrop();
    initDateHandling();
}); 