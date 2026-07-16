/**
 * Online Library Management System
 * Modern UI/UX JavaScript Framework
 */

class UI {
    static toast(message, type = 'info', duration = 3000) {
        const container = document.querySelector('.toast-container') || this.createToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = {
            success: '<i class="bi bi-check-circle"></i>',
            error: '<i class="bi bi-exclamation-circle"></i>',
            warning: '<i class="bi bi-exclamation-triangle"></i>',
            info: '<i class="bi bi-info-circle"></i>'
        };
        
        toast.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                ${icon[type] || icon.info}
                <div>${message}</div>
                <button class="btn-close" onclick="this.parentElement.parentElement.remove()" style="margin-left: auto;"></button>
            </div>
        `;
        
        container.appendChild(toast);
        
        if (duration) {
            setTimeout(() => toast.remove(), duration);
        }
        
        return toast;
    }
    
    static createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
        return container;
    }
    
    static showLoader(element) {
        element.innerHTML = `
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        `;
    }
    
    static hideLoader(element, content) {
        element.innerHTML = content;
    }
    
    static animateCounter(element, target, duration = 1000) {
        const start = 0;
        const increment = target / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            if (current >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, 16);
    }
}

// Dark Mode Toggle
class DarkMode {
    static init() {
        // Apply saved theme immediately (also done in base.html FOUC script)
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
            document.documentElement.classList.remove('dark');
        }
        
        // Find all theme toggles (navbar + any other)
        const toggles = document.querySelectorAll('#themeToggle, #adminThemeToggle');
        if (toggles.length === 0) return;
        
        // Attach click to all toggles
        toggles.forEach(toggle => {
            toggle.addEventListener('click', () => this.toggle());
        });
    }
    
    static toggle() {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'light');
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        }
    }
}

// Smooth Scroll
document.addEventListener('DOMContentLoaded', () => {
    DarkMode.init();
    
    // Animate elements on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-fade-in');
            }
        });
    }, { threshold: 0.1 });
    
    document.querySelectorAll('[data-animate]').forEach(el => {
        observer.observe(el);
    });
    
    // Smooth link scrolling
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', (e) => {
            const target = document.querySelector(link.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});
