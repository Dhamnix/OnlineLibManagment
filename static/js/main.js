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
        const toggle = document.querySelector('[data-toggle-darkmode]');
        if (!toggle) return;
        
        const isDark = localStorage.getItem('darkmode') === 'true';
        if (isDark) this.enable();
        
        toggle.addEventListener('click', () => this.toggle());
    }
    
    static toggle() {
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        isDark ? this.disable() : this.enable();
    }
    
    static enable() {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
        localStorage.setItem('darkmode', 'true');
    }
    
    static disable() {
        document.documentElement.removeAttribute('data-bs-theme');
        localStorage.setItem('darkmode', 'false');
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
