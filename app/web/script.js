// Nanotech.icu Website JavaScript

document.addEventListener('DOMContentLoaded', function() {
    console.log('Nanotech.icu Website loaded successfully!');

    initThemeToggle();
    initMobileMenu();
    initSmoothScrolling();
    initScrollAnimations();
    initContactForm();
    initROICalculator();
    initParticleAnimation();
    initCounterAnimations();
    initIntersectionObserver();
    initHeaderScroll();
    initChatWidget();
    initAdvancedVisuals();
    initAuth();
    initScrollProgress();
    initTestimonials();
    initFAQ();
    initPaymentIcons();
    initScrollReveal();
});

// Theme Toggle Functionality
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeStyleSelect = document.getElementById('theme-style-select');
    const body = document.body;

    if (!themeToggle) return;

    const allowedStyles = ['light', 'dark', 'aurora', 'glass'];
    const savedStyle = localStorage.getItem('theme_style') || localStorage.getItem('theme') || 'light';
    applyThemeStyle(savedStyle);

    if (themeStyleSelect) {
        themeStyleSelect.value = body.dataset.themeStyle || 'light';
        themeStyleSelect.addEventListener('change', function() {
            applyThemeStyle(themeStyleSelect.value);
        });
    }

    themeToggle.addEventListener('click', function() {
        const currentStyle = body.dataset.themeStyle || 'light';
        const nextStyle = currentStyle === 'dark' ? 'light' : 'dark';
        applyThemeStyle(nextStyle);
        if (themeStyleSelect) themeStyleSelect.value = nextStyle;

        themeToggle.style.transform = 'scale(0.8)';
        setTimeout(() => {
            themeToggle.style.transform = 'scale(1)';
        }, 150);
    });

    function applyThemeStyle(style) {
        const normalized = allowedStyles.includes(style) ? style : 'light';
        body.dataset.themeStyle = normalized;
        body.classList.toggle('dark-mode', normalized === 'dark');
        updateThemeIcon(normalized === 'dark' ? 'dark' : 'light');
        localStorage.setItem('theme_style', normalized);
        localStorage.setItem('theme', normalized === 'dark' ? 'dark' : 'light');
    }
}

function updateThemeIcon(theme) {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;
    const icon = themeToggle.querySelector('i');
    if (!icon) return;

    if (theme === 'dark') {
        icon.className = 'fas fa-sun';
    } else {
        icon.className = 'fas fa-moon';
    }
}

// Mobile Menu Functionality
function initMobileMenu() {
    const navToggle = document.getElementById('nav-toggle');
    const navMenu = document.getElementById('nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');

    navToggle.addEventListener('click', function() {
        navMenu.classList.toggle('active');
        navToggle.classList.toggle('active');

        // Prevent body scroll when menu is open
        document.body.style.overflow = navMenu.classList.contains('active') ? 'hidden' : 'auto';
    });

    // Close menu when clicking on a link
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
            document.body.style.overflow = 'auto';
        });
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    });

    document.querySelectorAll('.has-dropdown > .nav-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            if (window.innerWidth <= 768) {
                e.preventDefault();
                var li = link.parentElement;
                document.querySelectorAll('.has-dropdown').forEach(function(d) { if (d !== li) d.classList.remove('open'); });
                li.classList.toggle('open');
            }
        });
    });
}

// Smooth Scrolling
function initSmoothScrolling() {
    const navLinks = document.querySelectorAll('a[href^="#"]');

    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);

            if (targetSection) {
                const headerHeight = document.querySelector('.header').offsetHeight;
                const targetPosition = targetSection.offsetTop - headerHeight;

                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// Scroll Animations
function initScrollAnimations() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');

    // Add active class to navigation links based on scroll position
    window.addEventListener('scroll', function() {
        const scrollPos = window.scrollY + 200;

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.offsetHeight;
            const sectionId = section.getAttribute('id');

            if (scrollPos >= sectionTop && scrollPos < sectionTop + sectionHeight) {
                // Remove active class from all nav links
                navLinks.forEach(link => link.classList.remove('active'));

                // Add active class to current section's nav link
                const activeLink = document.querySelector(`.nav-link[href="#${sectionId}"]`);
                if (activeLink) {
                    activeLink.classList.add('active');
                }
            }
        });
    });
}

// Header Scroll Behavior
function initHeaderScroll() {
    const header = document.querySelector('.header');
    let lastScrollY = window.scrollY;

    window.addEventListener('scroll', function() {
        const currentScrollY = window.scrollY;

        if (currentScrollY > 100) {
            header.style.background = 'rgba(255, 255, 255, 0.98)';
            header.style.backdropFilter = 'blur(20px)';
        } else {
            header.style.background = 'rgba(255, 255, 255, 0.95)';
            header.style.backdropFilter = 'blur(10px)';
        }

        if (document.body.classList.contains('dark-mode')) {
            if (currentScrollY > 100) {
                header.style.background = 'rgba(17, 24, 39, 0.98)';
            } else {
                header.style.background = 'rgba(17, 24, 39, 0.95)';
            }
        }

        lastScrollY = currentScrollY;
    });
}

// Contact Form Functionality
function initContactForm() {
    const contactForm = document.getElementById('contact-form');

    contactForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Get form data
        const formData = new FormData(contactForm);
        const data = Object.fromEntries(formData);

        // Validate form
        if (!validateForm(data)) {
            return;
        }

        // Show loading state
        const submitBtn = contactForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.textContent = 'Sending...';
        submitBtn.disabled = true;

        fetch('/api/contact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(r) { return r.json().then(function(res) { return { status: r.status, res: res }; }); })
        .then(function(payload) {
            var res = payload.res || {};
            if (res.ok && res.email_sent !== false) {
                showNotification('Message sent successfully! We\'ll get back to you soon.', 'success');
                contactForm.reset();
            } else {
                showNotification(
                    res.error || 'Failed to send message. Please email info@nanotech.icu directly.',
                    'error'
                );
            }
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        })
        .catch(function() {
            showNotification('Network error. Please try again or email info@nanotech.icu.', 'error');
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        });
    });

    // Add floating label effect
    const formGroups = document.querySelectorAll('.form-group');
    formGroups.forEach(group => {
        const input = group.querySelector('input, select, textarea');
        const label = group.querySelector('label');

        if (input && label) {
            input.addEventListener('focus', function() {
                label.style.transform = 'translateY(-1.5rem) scale(0.875)';
            });

            input.addEventListener('blur', function() {
                if (!input.value) {
                    label.style.transform = 'translateY(0) scale(1)';
                }
            });
        }
    });
}

function initROICalculator() {
    const form = document.getElementById('roi-calculator-form');
    const results = document.getElementById('roi-results');
    const monthlySavingsEl = document.getElementById('roi-monthly-savings');
    const annualBenefitEl = document.getElementById('roi-annual-benefit');
    const paybackEl = document.getElementById('roi-payback');
    const summaryEl = document.getElementById('roi-summary');
    const downloadResultBtn = document.getElementById('roi-download-result');
    const quoteBtn = document.getElementById('quote-cta-btn');
    const downloadCtaBtn = document.getElementById('download-roi-cta-btn');
    const contactMessage = document.getElementById('message');
    const serviceField = document.getElementById('service');

    if (!form || !results || !monthlySavingsEl || !annualBenefitEl || !paybackEl || !summaryEl || !downloadResultBtn) {
        return;
    }

    const currency = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
    });

    let latest = null;

    function num(id) {
        const el = document.getElementById(id);
        const value = el ? Number(el.value) : NaN;
        return Number.isFinite(value) ? value : NaN;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const hours = num('roi-hours');
        const hourlyRate = num('roi-hourly-rate');
        const automationPercent = num('roi-automation');
        const softwareCost = num('roi-software-cost');
        const setupCost = num('roi-setup-cost');

        if (
            !Number.isFinite(hours) ||
            !Number.isFinite(hourlyRate) ||
            !Number.isFinite(automationPercent) ||
            !Number.isFinite(softwareCost) ||
            !Number.isFinite(setupCost) ||
            hours <= 0 ||
            hourlyRate <= 0 ||
            automationPercent <= 0 ||
            automationPercent > 100 ||
            softwareCost < 0 ||
            setupCost < 0
        ) {
            showNotification('Enter valid ROI values to calculate.', 'error');
            return;
        }

        const currentMonthlyCost = hours * hourlyRate;
        const monthlySavings = currentMonthlyCost * (automationPercent / 100) - softwareCost;
        const annualNetBenefit = monthlySavings * 12 - setupCost;
        const paybackMonths = monthlySavings > 0 ? setupCost / monthlySavings : null;

        monthlySavingsEl.textContent = currency.format(monthlySavings);
        annualBenefitEl.textContent = currency.format(annualNetBenefit);
        paybackEl.textContent = paybackMonths ? `${paybackMonths.toFixed(1)} months` : 'No payback';

        const summary =
            `Estimated monthly savings: ${currency.format(monthlySavings)}. ` +
            `Estimated annual net benefit: ${currency.format(annualNetBenefit)}.`;
        summaryEl.textContent = summary;
        results.hidden = false;

        latest = {
            hours,
            hourlyRate,
            automationPercent,
            softwareCost,
            setupCost,
            monthlySavings,
            annualNetBenefit,
            paybackMonths,
            summary,
        };
    });

    if (quoteBtn) {
        quoteBtn.addEventListener('click', function() {
            if (!latest || !contactMessage) return;
            if (serviceField && !serviceField.value) {
                serviceField.value = 'analysis';
            }
            contactMessage.value = [
                'Hi NanoTech team, I want a custom automation quote.',
                '',
                'ROI snapshot:',
                `- Manual hours/month: ${latest.hours}`,
                `- Hourly cost: ${currency.format(latest.hourlyRate)}`,
                `- Automation: ${latest.automationPercent}%`,
                `- Estimated monthly savings: ${currency.format(latest.monthlySavings)}`,
                `- Estimated annual net benefit: ${currency.format(latest.annualNetBenefit)}`,
            ].join('\n');
        });
    }

    if (downloadCtaBtn) {
        downloadCtaBtn.addEventListener('click', function() {
            setTimeout(function() {
                const first = document.getElementById('roi-hours');
                if (first) first.focus();
            }, 350);
        });
    }

    downloadResultBtn.addEventListener('click', function() {
        if (!latest) {
            showNotification('Calculate ROI first, then download the summary.', 'error');
            return;
        }

        const content = [
            'NanoTech Hub - ROI Summary',
            '',
            `Manual hours/month: ${latest.hours}`,
            `Hourly cost: ${currency.format(latest.hourlyRate)}`,
            `Automation coverage: ${latest.automationPercent}%`,
            `Monthly software/tool cost: ${currency.format(latest.softwareCost)}`,
            `One-time setup cost: ${currency.format(latest.setupCost)}`,
            '',
            `Estimated monthly savings: ${currency.format(latest.monthlySavings)}`,
            `Estimated annual net benefit: ${currency.format(latest.annualNetBenefit)}`,
            `Estimated payback: ${latest.paybackMonths ? `${latest.paybackMonths.toFixed(1)} months` : 'No payback'}`,
        ].join('\n');

        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const href = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = href;
        link.download = 'nanotech-roi-summary.txt';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(href);
    });
}

function validateForm(data) {
    const requiredFields = ['name', 'email', 'service', 'message'];
    const errors = [];

    requiredFields.forEach(field => {
        if (!data[field] || data[field].trim() === '') {
            errors.push(`${field.charAt(0).toUpperCase() + field.slice(1)} is required`);
        }
    });

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (data.email && !emailRegex.test(data.email)) {
        errors.push('Please enter a valid email address');
    }

    if (errors.length > 0) {
        showNotification(errors.join('. '), 'error');
        return false;
    }

    return true;
}

function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => notification.remove());

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;

    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.5rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        z-index: 10000;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        max-width: 400px;
    `;

    // Add to DOM
    document.body.appendChild(notification);

    // Animate in
    setTimeout(() => {
        notification.style.transform = 'translateX(0)';
    }, 100);

    // Auto remove after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }
    }, 3000);
}

// Particle Animation
function initParticleAnimation() {
    const particles = document.querySelectorAll('.particle');

    particles.forEach((particle, index) => {
        // Add random movement
        setInterval(() => {
            const randomX = Math.random() * 20 - 10;
            const randomY = Math.random() * 20 - 10;

            particle.style.transform = `translate(${randomX}px, ${randomY}px)`;
        }, 3000 + index * 500);
    });
}

// Counter Animations
function initCounterAnimations() {
    const counters = document.querySelectorAll('.stat h3');

    const animateCounter = (counter) => {
        const target = parseInt(counter.textContent.replace(/\D/g, ''));
        const increment = target / 100;
        let current = 0;

        const updateCounter = () => {
            if (current < target) {
                current += increment;
                counter.textContent = Math.ceil(current) + (counter.textContent.includes('+') ? '+' : '');
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = counter.textContent;
            }
        };

        updateCounter();
    };

    // Intersection Observer for counter animation
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => {
        counterObserver.observe(counter);
    });
}

// Intersection Observer for scroll animations
function initIntersectionObserver() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe elements for animation
    const animateElements = document.querySelectorAll('.service-card, .research-area, .stat, .contact-item');
    animateElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
}

// Service Card Hover Effects
document.addEventListener('DOMContentLoaded', function() {
    const serviceCards = document.querySelectorAll('.service-card');

    serviceCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
});

// Research Area Hover Effects
document.addEventListener('DOMContentLoaded', function() {
    const researchAreas = document.querySelectorAll('.research-area');

    researchAreas.forEach(area => {
        area.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(15px)';
            this.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.1)';
        });

        area.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
            this.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
        });
    });
});

// Contact Item Hover Effects
document.addEventListener('DOMContentLoaded', function() {
    const contactItems = document.querySelectorAll('.contact-item');

    contactItems.forEach(item => {
        item.addEventListener('mouseenter', function() {
            this.style.transform = 'translateX(15px)';
            this.style.background = 'var(--bg-primary)';
        });

        item.addEventListener('mouseleave', function() {
            this.style.transform = 'translateX(0)';
            this.style.background = 'var(--bg-secondary)';
        });
    });
});

// Utility Functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Add scroll event listener with throttling
window.addEventListener('scroll', throttle(function() {
    // Additional scroll-based animations can be added here
}, 100));

// Add resize event listener with debouncing
window.addEventListener('resize', debounce(function() {
    // Handle responsive adjustments
    const navMenu = document.getElementById('nav-menu');
    const navToggle = document.getElementById('nav-toggle');

    if (window.innerWidth > 768) {
        navMenu.classList.remove('active');
        navToggle.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}, 250));

// Performance optimization: Preload critical resources
function preloadResources() {
    const criticalImages = [
        // Add any critical image URLs here
    ];

    criticalImages.forEach(src => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.href = src;
        document.head.appendChild(link);
    });
}

// Initialize preloading
preloadResources();

// Add keyboard navigation support
document.addEventListener('keydown', function(e) {
    // Close mobile menu with Escape key
    if (e.key === 'Escape') {
        const navMenu = document.getElementById('nav-menu');
        const navToggle = document.getElementById('nav-toggle');

        if (navMenu.classList.contains('active')) {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    }

    // Toggle theme with Ctrl/Cmd + D
    if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        document.getElementById('theme-toggle').click();
    }
});

// Add loading animation
window.addEventListener('load', function() {
    document.body.classList.add('loaded');

    // Remove any loading spinners or overlays
    const loaders = document.querySelectorAll('.loader, .loading');
    loaders.forEach(loader => loader.remove());
});

function initChatWidget() {
    const chatToggle = document.getElementById('chat-toggle');
    const chatWindow = document.getElementById('chat-window');
    const chatClose = document.getElementById('chat-close');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const chatBadge = document.querySelector('.chat-badge');
    const agentBar = document.getElementById('chat-agent-bar');
    const attachBtn = document.getElementById('chat-attach-btn');
    const micBtn = document.getElementById('chat-mic-btn');
    const fileInput = document.getElementById('chat-file-input');
    const attachmentsContainer = document.getElementById('chat-attachments');
    const resizeTopHandle = document.getElementById('chat-resize-top');
    const resizeLeftHandle = document.getElementById('chat-resize-left');
    const chatMaximize = document.getElementById('chat-maximize');
    const chatStop = document.getElementById('chat-stop');
    const chatReset = document.getElementById('chat-reset');
    const quickReplies = document.querySelectorAll('.quick-reply');
    const chatConsentOverlay = document.getElementById('chat-consent-overlay');
    const chatConsentClose = document.getElementById('chat-consent-close');
    const chatConsentCancel = document.getElementById('chat-consent-cancel');
    const chatConsentCheckbox = document.getElementById('chat-consent-checkbox');
    const chatConsentAgree = document.getElementById('chat-consent-agree');
    let selectedAgent = 'auto';

    if (!chatToggle || !chatWindow || !chatClose || !chatForm || !chatInput || !chatMessages) return;

    let isOpen = false;
    let isMaximized = false;
    let isSending = false;
    let currentAbort = null;
    let pendingFiles = [];
    const maxAttachments = 4;
    const maxFileBytes = 25 * 1024 * 1024;
    const maxFileSizeLabel = `${Math.round(maxFileBytes / (1024 * 1024))}MB`;
    const maxTextChars = 12000;
    const minChatHeight = 420;
    const maxChatHeight = 860;
    const minChatWidth = 320;
    const maxChatWidth = 700;
    const chatConsentStorageKey = 'nanotech_ai_chat_terms_accepted';
    const chatConsentCookieName = 'nanotech_ai_chat_terms_accepted';
    const chatConsentVersion = '2026-03-09';
    let resizeState = null;
    let pendingConsentSource = 'chat_toggle';

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isListening = false;
    let chatConsent = readStoredChatConsent();

    function safeLocalStorageGet(key) {
        try {
            return localStorage.getItem(key);
        } catch (_) {
            return '';
        }
    }

    function safeLocalStorageSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (_) {
        }
    }

    function getCookieValue(name) {
        const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
        return match ? decodeURIComponent(match[1]) : '';
    }

    function readStoredChatConsent() {
        const raw = safeLocalStorageGet(chatConsentStorageKey);
        if (raw) {
            try {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.accepted && parsed.version === chatConsentVersion) {
                    return parsed;
                }
            } catch (_) {
                if (raw === 'true') return { accepted: true, version: chatConsentVersion };
            }
        }

        const cookieValue = getCookieValue(chatConsentCookieName);
        if (cookieValue === chatConsentVersion || cookieValue === 'true') {
            return { accepted: true, version: chatConsentVersion };
        }

        return { accepted: false, version: null };
    }

    function persistChatConsent(acceptedAt) {
        chatConsent = {
            accepted: true,
            version: chatConsentVersion,
            acceptedAt: acceptedAt,
        };
        safeLocalStorageSet(chatConsentStorageKey, JSON.stringify(chatConsent));
        document.cookie = `${chatConsentCookieName}=${encodeURIComponent(chatConsentVersion)}; Max-Age=31536000; Path=/; SameSite=Lax`;
    }

    function syncChatConsentUi() {
        const locked = !(chatConsent && chatConsent.accepted);
        chatInput.readOnly = locked;
        chatInput.classList.toggle('locked', locked);
        chatInput.placeholder = locked ? 'Review AI Chat Terms to start typing...' : 'Type your message...';
    }

    function openConsentModal(source) {
        pendingConsentSource = source || 'chat_toggle';
        if (!chatConsentOverlay) {
            showNotification('Please review the AI chat terms before using the assistant.', 'info');
            return false;
        }
        chatConsentOverlay.classList.add('open');
        chatConsentOverlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('chat-consent-open');
        if (chatConsentCheckbox) chatConsentCheckbox.focus();
        return true;
    }

    function closeConsentModal() {
        if (!chatConsentOverlay) return;
        chatConsentOverlay.classList.remove('open');
        chatConsentOverlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('chat-consent-open');
        if (chatConsentCheckbox) chatConsentCheckbox.checked = false;
        if (chatConsentAgree) chatConsentAgree.disabled = true;
    }

    function ensureChatConsent(source, event) {
        if (chatConsent && chatConsent.accepted) return true;
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        openConsentModal(source);
        return false;
    }

    async function logChatConsent(acceptedAt) {
        const headers = { 'Content-Type': 'application/json' };
        const authToken = safeLocalStorageGet('auth_token');
        if (authToken) headers.Authorization = `Bearer ${authToken}`;

        const response = await fetch('/api/chat-consent', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                accepted_at: acceptedAt,
                consent_version: chatConsentVersion,
                source: pendingConsentSource,
                path: window.location.pathname,
                locale: navigator.language || '',
            })
        });

        if (!response.ok) {
            throw new Error(`consent_log_failed_${response.status}`);
        }
    }

    function openChat(shouldFocusInput) {
        if (isOpen) {
            if (shouldFocusInput && chatConsent && chatConsent.accepted) chatInput.focus();
            return;
        }

        isOpen = true;
        chatWindow.classList.add('active');
        chatToggle.classList.add('active');
        applyChatHeight(parseFloat(chatWindow.style.height) || chatWindow.offsetHeight);

        if (chatBadge) {
            chatBadge.style.display = 'none';
        }

        if (shouldFocusInput && chatConsent && chatConsent.accepted) {
            chatInput.focus();
        }
    }

    function closeChat() {
        if (!isOpen) return;
        isOpen = false;
        chatWindow.classList.remove('active');
        chatToggle.classList.remove('active');
    }

    chatToggle.addEventListener('click', function() {
        if (isOpen) {
            closeChat();
            return;
        }
        if (!chatConsent.accepted) {
            openConsentModal('chat_toggle');
            return;
        }
        openChat(true);
    });

    chatClose.addEventListener('click', function() {
        closeChat();
    });

    if (chatMaximize) {
        chatMaximize.addEventListener('click', function() {
            toggleMaximize();
        });
    }

    function toggleMaximize() {
        isMaximized = !isMaximized;
        chatWindow.classList.toggle('maximized', isMaximized);
        const icon = chatMaximize.querySelector('i');
        if (icon) {
            icon.className = isMaximized ? 'fas fa-compress-arrows-alt' : 'fas fa-expand-arrows-alt';
        }
    }

    if (chatStop) {
        chatStop.addEventListener('click', function() {
            if (currentAbort) {
                currentAbort.abort();
                currentAbort = null;
            }
            isSending = false;
            chatStop.classList.remove('visible');
            hideTypingIndicator();
        });
    }

    if (chatReset) {
        chatReset.addEventListener('click', function() {
            if (currentAbort) {
                currentAbort.abort();
                currentAbort = null;
            }
            isSending = false;
            if (chatStop) chatStop.classList.remove('visible');
            chatMessages.innerHTML = '<div class="chat-message bot-message"><div class="message-avatar"><i class="fas fa-robot"></i></div><div class="message-content"><p>\uD83D\uDC4B Hi! I\'m your AI assistant at NanoTech Hub.</p><p>How can I help you today?</p></div></div>';
            chatInput.value = '';
            pendingFiles = [];
            renderPendingFiles();
        });
    }

    var seeAiBtn = document.getElementById('see-ai-action-btn');
    if (seeAiBtn) {
        seeAiBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (!isOpen) openChat(chatConsent.accepted);
            if (chatConsent.accepted) {
                if (!isMaximized) toggleMaximize();
                return;
            }
            showNotification('Review the AI Chat Terms in the chat window before sending a message.', 'info');
        });
    }

    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (!ensureChatConsent('chat_submit', e)) return;

        if (isSending) return;

        const message = chatInput.value.trim();
        if (!message && !pendingFiles.length) return;

        const queuedFiles = pendingFiles.slice();
        const attachmentSummary = queuedFiles.map(file => ({
            name: file.name,
            type: file.type,
            size: file.size,
            kind: file.type.startsWith('image/') ? 'image' : 'file',
        }));

        isSending = true;
        if (recognition && isListening) recognition.stop();

        try {
            const attachments = await serializeAttachments(queuedFiles);
            addUserMessage(message, attachmentSummary);
            chatInput.value = '';
            pendingFiles = [];
            renderPendingFiles();
            showTypingIndicator();
            await handleBotResponse(message, attachments);
        } catch (error) {
            hideTypingIndicator();
            addBotMessage('Could not read one of the selected files. Please try again.');
        } finally {
            isSending = false;
        }
    });

    function addFiles(files) {
        if (!files || !files.length) return;
        let limitHit = false;
        let oversized = false;

        Array.from(files).forEach(file => {
            if (pendingFiles.length >= maxAttachments) { limitHit = true; return; }
            if (file.size > maxFileBytes) { oversized = true; return; }
            const duplicate = pendingFiles.some(item => (
                item.name === file.name && item.size === file.size && item.lastModified === file.lastModified
            ));
            if (!duplicate) pendingFiles.push(file);
        });

        renderPendingFiles();
        if (limitHit) showNotification(`Maximum ${maxAttachments} files per message.`, 'info');
        if (oversized) showNotification(`Each file must be ${maxFileSizeLabel} or less.`, 'error');
    }

    if (attachBtn && fileInput) {
        attachBtn.addEventListener('click', function(e) {
            if (!ensureChatConsent('chat_attachment', e)) return;
            fileInput.click();
        });
        fileInput.addEventListener('change', function() {
            addFiles(fileInput.files);
            fileInput.value = '';
        });
    }

    chatInput.addEventListener('pointerdown', function(e) {
        if (!chatConsent.accepted) {
            e.preventDefault();
            openConsentModal('chat_input_focus');
        }
    });

    chatInput.addEventListener('focus', function() {
        if (!chatConsent.accepted) {
            chatInput.blur();
            openConsentModal('chat_input_focus');
        }
    });

    const chatInputContainer = chatWindow.querySelector('.chat-input-container') || chatWindow;
    chatInputContainer.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        chatInputContainer.classList.add('drag-over');
    });
    chatInputContainer.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        chatInputContainer.classList.remove('drag-over');
    });
    chatInputContainer.addEventListener('drop', function(e) {
        if (!chatConsent.accepted) {
            ensureChatConsent('chat_drop', e);
            chatInputContainer.classList.remove('drag-over');
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        chatInputContainer.classList.remove('drag-over');
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
            addFiles(e.dataTransfer.files);
        }
    });

    const voiceLangs = [
        {code: '', label: 'Auto'},
        {code: 'en-US', label: 'EN'},
        {code: 'es-ES', label: 'ES'},
        {code: 'ru-RU', label: 'RU'},
        {code: 'zh-CN', label: '中文'},
        {code: 'hi-IN', label: 'HI'},
        {code: 'ar-SA', label: 'AR'},
        {code: 'pt-BR', label: 'PT'},
        {code: 'fr-FR', label: 'FR'},
        {code: 'de-DE', label: 'DE'},
    ];
    let voiceLangIndex = 0;

    if (micBtn) {
        if (SpeechRecognition) {
            recognition = new SpeechRecognition();
            recognition.lang = voiceLangs[0].code;
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;
            recognition.continuous = false;

            const langBadge = document.createElement('span');
            langBadge.className = 'mic-lang-badge';
            langBadge.textContent = voiceLangs[0].label;
            micBtn.style.position = 'relative';
            micBtn.appendChild(langBadge);

            recognition.onstart = function() {
                isListening = true;
                micBtn.classList.add('active');
            };

            recognition.onend = function() {
                isListening = false;
                micBtn.classList.remove('active');
            };

            recognition.onresult = function(event) {
                const spoken = event && event.results && event.results[0] && event.results[0][0]
                    ? event.results[0][0].transcript.trim()
                    : '';
                if (!spoken) return;
                const current = chatInput.value.trim();
                chatInput.value = current ? `${current} ${spoken}` : spoken;
                chatInput.focus();
            };

            recognition.onerror = function() {
                isListening = false;
                micBtn.classList.remove('active');
            };

            micBtn.addEventListener('click', function(e) {
                if (!ensureChatConsent('chat_voice', e)) return;
                if (isListening) recognition.stop();
                else {
                    recognition.lang = voiceLangs[voiceLangIndex].code;
                    recognition.start();
                }
            });

            micBtn.addEventListener('contextmenu', function(e) {
                if (!ensureChatConsent('chat_voice', e)) return;
                e.preventDefault();
                if (isListening) recognition.stop();
                voiceLangIndex = (voiceLangIndex + 1) % voiceLangs.length;
                const lang = voiceLangs[voiceLangIndex];
                recognition.lang = lang.code;
                langBadge.textContent = lang.label;
                showNotification(`Voice language: ${lang.label}`, 'info');
            });
        } else {
            micBtn.disabled = true;
            micBtn.setAttribute('aria-disabled', 'true');
            micBtn.title = 'Voice input is not supported in this browser';
        }
    }

    quickReplies.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!ensureChatConsent('chat_quick_reply', e)) return;
            const message = this.dataset.message;
            addUserMessage(message, []);

            const container = this.closest('.chat-quick-replies');
            if (container) container.style.display = 'none';

            showTypingIndicator();
            handleBotResponse(message, []);
        });
    });

    initChatResize();
    renderPendingFiles();
    syncChatConsentUi();

    if (chatConsentCheckbox) {
        chatConsentCheckbox.addEventListener('change', function() {
            if (chatConsentAgree) chatConsentAgree.disabled = !chatConsentCheckbox.checked;
        });
    }

    if (chatConsentClose) {
        chatConsentClose.addEventListener('click', closeConsentModal);
    }

    if (chatConsentCancel) {
        chatConsentCancel.addEventListener('click', closeConsentModal);
    }

    if (chatConsentOverlay) {
        chatConsentOverlay.addEventListener('click', function(e) {
            if (e.target === chatConsentOverlay) closeConsentModal();
        });
    }

    if (chatConsentAgree) {
        chatConsentAgree.addEventListener('click', async function() {
            if (!chatConsentCheckbox || !chatConsentCheckbox.checked) return;

            const acceptedAt = new Date().toISOString();
            persistChatConsent(acceptedAt);
            syncChatConsentUi();
            closeConsentModal();

            try {
                await logChatConsent(acceptedAt);
            } catch (error) {
                console.error('Consent log error:', error);
            }

            if (!isOpen) openChat(true);
            else chatInput.focus();
        });
    }

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && chatConsentOverlay && chatConsentOverlay.classList.contains('open')) {
            closeConsentModal();
        }
    });

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function parseInlineMarkdown(text) {
        const codeSpans = [];
        let rendered = text.replace(/`([^`\n]+)`/g, function(_, code) {
            const index = codeSpans.push(`<code>${code}</code>`) - 1;
            return `\u0000CODE${index}\u0000`;
        });

        rendered = rendered
            .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
            .replace(/__([^_\n]+)__/g, '<strong>$1</strong>')
            .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
            .replace(/(^|[^_])_([^_\n]+)_/g, '$1<em>$2</em>');

        return rendered.replace(/\u0000CODE(\d+)\u0000/g, function(_, index) {
            return codeSpans[Number(index)] || '';
        });
    }

    function parseMarkdown(text) {
        const lines = escapeHtml(text).replace(/\r\n?/g, '\n').split('\n');
        const html = [];
        let paragraph = [];
        let listType = '';
        let inCodeBlock = false;
        let codeLines = [];

        function closeParagraph() {
            if (!paragraph.length) return;
            html.push(`<p>${paragraph.map(parseInlineMarkdown).join('<br>')}</p>`);
            paragraph = [];
        }

        function closeList() {
            if (!listType) return;
            html.push(`</${listType}>`);
            listType = '';
        }

        lines.forEach(function(line) {
            if (/^\s*```/.test(line)) {
                closeParagraph();
                closeList();
                if (inCodeBlock) {
                    html.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
                    codeLines = [];
                }
                inCodeBlock = !inCodeBlock;
                return;
            }

            if (inCodeBlock) {
                codeLines.push(line);
                return;
            }

            if (!line.trim()) {
                closeParagraph();
                closeList();
                return;
            }

            const heading = line.match(/^\s*(#{1,4})\s+(.+)$/);
            if (heading) {
                closeParagraph();
                closeList();
                const level = Math.min(4, heading[1].length + 2);
                html.push(`<h${level}>${parseInlineMarkdown(heading[2])}</h${level}>`);
                return;
            }

            const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
            const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
            if (unordered || ordered) {
                closeParagraph();
                const nextListType = unordered ? 'ul' : 'ol';
                if (listType !== nextListType) {
                    closeList();
                    listType = nextListType;
                    html.push(`<${listType}>`);
                }
                html.push(`<li>${parseInlineMarkdown((unordered || ordered)[1])}</li>`);
                return;
            }

            closeList();
            paragraph.push(line);
        });

        if (inCodeBlock && codeLines.length) {
            html.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
        }
        closeParagraph();
        closeList();
        return html.join('');
    }

    function renderPendingFiles() {
        if (!attachmentsContainer) return;

        attachmentsContainer.innerHTML = '';
        pendingFiles.forEach((file, index) => {
            const chip = document.createElement('div');
            chip.className = 'chat-attachment-chip';
            const iconClass = file.type.startsWith('image/') ? 'fa-image' : 'fa-file';
            chip.innerHTML = `
                <i class="fas ${iconClass}"></i>
                <span class="chip-name">${escapeHtml(file.name)}</span>
                <button type="button" class="chat-attachment-remove" data-index="${index}" aria-label="Remove file">&times;</button>
            `;
            attachmentsContainer.appendChild(chip);
        });

        attachmentsContainer.querySelectorAll('.chat-attachment-remove').forEach(btn => {
            btn.addEventListener('click', function() {
                const index = Number(this.dataset.index);
                if (!Number.isInteger(index)) return;
                pendingFiles.splice(index, 1);
                renderPendingFiles();
            });
        });
    }

    function initChatResize() {
        const savedHeight = Number(localStorage.getItem('chat_window_height'));
        applyChatHeight(Number.isFinite(savedHeight) ? savedHeight : chatWindow.offsetHeight);
        const savedWidth = Number(localStorage.getItem('chat_window_width'));
        applyChatWidth(Number.isFinite(savedWidth) ? savedWidth : chatWindow.offsetWidth);

        if (resizeTopHandle) {
            resizeTopHandle.addEventListener('pointerdown', function(event) {
                startResize('top', event);
            });
        }

        if (resizeLeftHandle) {
            resizeLeftHandle.addEventListener('pointerdown', function(event) {
                startResize('left', event);
            });
        }

        window.addEventListener('resize', function() {
            if (window.innerWidth <= 480) {
                chatWindow.style.height = '';
                chatWindow.style.width = '';
                return;
            }
            const currentHeight = parseFloat(chatWindow.style.height) || chatWindow.offsetHeight;
            applyChatHeight(currentHeight);
            const currentWidth = parseFloat(chatWindow.style.width) || chatWindow.offsetWidth;
            applyChatWidth(currentWidth);
        });
    }

    function getMaxChatHeight() {
        const viewportLimit = window.innerHeight - 110;
        return Math.max(minChatHeight, Math.min(maxChatHeight, viewportLimit));
    }

    function getMaxChatWidth() {
        const viewportLimit = window.innerWidth - 40;
        return Math.max(minChatWidth, Math.min(maxChatWidth, viewportLimit));
    }

    function applyChatHeight(height) {
        if (window.innerWidth <= 480) return;
        const next = Number(height);
        const normalized = Number.isFinite(next) ? next : chatWindow.offsetHeight;
        const clamped = Math.max(minChatHeight, Math.min(getMaxChatHeight(), normalized));
        chatWindow.style.height = `${Math.round(clamped)}px`;
    }

    function applyChatWidth(width) {
        if (window.innerWidth <= 480) return;
        const next = Number(width);
        const normalized = Number.isFinite(next) ? next : chatWindow.offsetWidth;
        const clamped = Math.max(minChatWidth, Math.min(getMaxChatWidth(), normalized));
        chatWindow.style.width = `${Math.round(clamped)}px`;
    }

    function startResize(edge, event) {
        if (window.innerWidth <= 480) return;
        event.preventDefault();
        const rect = chatWindow.getBoundingClientRect();
        resizeState = {
            edge,
            startX: event.clientX,
            startY: event.clientY,
            startHeight: rect.height,
            startWidth: rect.width,
        };
        chatWindow.classList.add('resizing');
        document.body.classList.add('chat-window-resizing');
        document.body.classList.add(edge === 'left' ? 'chat-window-resizing-h' : 'chat-window-resizing-v');
        window.addEventListener('pointermove', onResizeMove);
        window.addEventListener('pointerup', stopResize);
        window.addEventListener('pointercancel', stopResize);
    }

    function onResizeMove(event) {
        if (!resizeState) return;
        if (resizeState.edge === 'top') {
            const deltaY = event.clientY - resizeState.startY;
            applyChatHeight(resizeState.startHeight - deltaY);
        } else if (resizeState.edge === 'left') {
            const deltaX = event.clientX - resizeState.startX;
            applyChatWidth(resizeState.startWidth - deltaX);
        }
    }

    function stopResize() {
        if (!resizeState) return;
        resizeState = null;
        chatWindow.classList.remove('resizing');
        document.body.classList.remove('chat-window-resizing', 'chat-window-resizing-v', 'chat-window-resizing-h');
        window.removeEventListener('pointermove', onResizeMove);
        window.removeEventListener('pointerup', stopResize);
        window.removeEventListener('pointercancel', stopResize);
        const finalHeight = parseFloat(chatWindow.style.height);
        if (Number.isFinite(finalHeight)) {
            localStorage.setItem('chat_window_height', String(Math.round(finalHeight)));
        }
        const finalWidth = parseFloat(chatWindow.style.width);
        if (Number.isFinite(finalWidth)) {
            localStorage.setItem('chat_window_width', String(Math.round(finalWidth)));
        }
    }

    function isTextFile(file) {
        if (!file) return false;
        if (typeof file.type === 'string' && file.type.startsWith('text/')) return true;
        const name = String(file.name || '').toLowerCase();
        return ['.txt', '.md', '.csv', '.json', '.xml', '.yml', '.yaml'].some(ext => name.endsWith(ext));
    }

    function readAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = function() {
                resolve(String(reader.result || ''));
            };
            reader.onerror = function() {
                reject(reader.error || new Error('file_read_error'));
            };
            reader.readAsDataURL(file);
        });
    }

    async function serializeAttachments(files) {
        const items = [];

        for (const file of files) {
            const base = {
                name: file.name,
                type: file.type || 'application/octet-stream',
                size: file.size,
            };

            if (file.type.startsWith('image/')) {
                const dataUrl = await readAsDataUrl(file);
                items.push({ ...base, kind: 'image', data_url: dataUrl });
                continue;
            }

            if (isTextFile(file)) {
                let text = await file.text();
                const truncated = text.length > maxTextChars;
                if (truncated) text = text.slice(0, maxTextChars);
                items.push({ ...base, kind: 'text', text, truncated });
                continue;
            }

            items.push({ ...base, kind: 'file' });
        }

        return items;
    }

    if (agentBar) {
        agentBar.addEventListener('click', function(e) {
            var btn = e.target.closest('.agent-btn');
            if (!btn) return;
            if (!ensureChatConsent('chat_agent_select', e)) return;
            agentBar.querySelectorAll('.agent-btn').forEach(function(b) { b.classList.remove('active'); });
            btn.classList.add('active');
            selectedAgent = btn.getAttribute('data-agent') || 'auto';
        });
    }

    function addUserMessage(text, attachments) {
        const safeText = text ? `<p>${escapeHtml(text)}</p>` : '';
        const names = Array.isArray(attachments)
            ? attachments.map(item => item && item.name).filter(Boolean)
            : [];
        const filesLine = names.length
            ? `<p>📎 ${escapeHtml(names.join(', '))}</p>`
            : '';

        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message user-message';
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="message-content">
                ${safeText || '<p>📎 Sent attachment(s)</p>'}
                ${filesLine}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function addBotMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message bot-message';
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content md-body">
                ${parseMarkdown(text)}
            </div>
        `;
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    function showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-message bot-message typing-indicator-msg';
        typingDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        chatMessages.appendChild(typingDiv);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const typingIndicator = chatMessages.querySelector('.typing-indicator-msg');
        if (typingIndicator) typingIndicator.remove();
    }

    async function handleBotResponse(userMessage, attachments) {
        currentAbort = new AbortController();
        if (chatStop) chatStop.classList.add('visible');
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: currentAbort.signal,
                body: JSON.stringify({
                    message: userMessage,
                    agent: selectedAgent,
                    attachments: Array.isArray(attachments) ? attachments : [],
                })
            });

            if (!response.ok) {
                let details = '';
                try {
                    const err = await response.json();
                    if (err && typeof err.message === 'string') details = err.message;
                    else if (err && typeof err.error === 'string') details = err.error;
                } catch (_) {
                }
                throw new Error(details || `HTTP ${response.status}`);
            }

            const data = await response.json();
            hideTypingIndicator();

            const reply = data && typeof data.reply === 'string' ? data.reply : '';
            addBotMessage(reply || "Sorry, I didn't get a response. Please try again.");

            if (data && data.model) {
                var info = document.createElement('div');
                info.className = 'chat-routed-info';
                info.textContent = data.model;
                chatMessages.appendChild(info);
            }

            const warning = data && typeof data.warning === 'string' ? data.warning : '';
            if (warning) addBotMessage(`Note: ${warning}`);
        } catch (error) {
            if (error && error.name === 'AbortError') {
                hideTypingIndicator();
                addBotMessage('Response stopped.');
            } else {
                console.error('Chat API Error:', error);
                hideTypingIndicator();
                const msg = error && typeof error.message === 'string' ? error.message : '';
                addBotMessage(msg || 'Chat is temporarily unavailable. Please email info@nanotech.icu.');
            }
        } finally {
            currentAbort = null;
            isSending = false;
            if (chatStop) chatStop.classList.remove('visible');
        }
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Auto-open chat after 2.5 seconds
    setTimeout(function() {
        if (!isOpen) {
            openChat(false);
        }
    }, 2500);
}

function initAdvancedVisuals() {
    var canvas = document.getElementById('hero-canvas');
    var heroVisual = document.getElementById('hero-visual');
    var tooltip = document.getElementById('hero-tooltip');
    if (!canvas || !heroVisual) return;
    var ctx = canvas.getContext('2d');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W, H, cx, cy, orbitRx, orbitRy;
    var mouseX = 0.5, mouseY = 0.5;
    var tiltX = 0, tiltY = 0;
    var time = 0;
    var entranceProgress = 0;
    var running = true;
    var hoveredNode = null;
    var isDark = document.body.classList.contains('dark-mode');

    var agents = [
        { label: 'DeepSeek', desc: 'Open-source reasoning model', color: '#6366f1', angle: 0 },
        { label: 'Perplexity', desc: 'AI-powered search engine', color: '#06b6d4', angle: 0 },
        { label: 'Meta AI', desc: 'Llama open models', color: '#0066cc', angle: 0 },
        { label: 'ChatGPT', desc: 'OpenAI flagship model', color: '#10b981', angle: 0 },
        { label: 'Gemini', desc: 'Google multimodal AI', color: '#4285f4', angle: 0 },
        { label: 'Kimi', desc: 'Long-context AI assistant', color: '#8b5cf6', angle: 0 },
        { label: 'Claude', desc: 'Anthropic reasoning model', color: '#d97706', angle: 0 },
        { label: 'Grok', desc: 'xAI real-time model', color: '#ef4444', angle: 0 },
        { label: 'Mistral', desc: 'European open-weight LLM', color: '#f59e0b', angle: 0 },
        { label: 'Qwen', desc: 'Alibaba multilingual model', color: '#ec4899', angle: 0 }
    ];
    var N = agents.length;
    for (var i = 0; i < N; i++) agents[i].angle = (i / N) * Math.PI * 2 - Math.PI / 2;

    var particles = [];
    var pulses = [];
    var blobs = [];
    var shootingStars = [];
    var galaxies = [];

    function resize() {
        var rect = canvas.getBoundingClientRect();
        W = Math.floor(rect.width * dpr);
        H = Math.floor(rect.height * dpr);
        canvas.width = W;
        canvas.height = H;
        cx = W / 2;
        cy = H / 2;
        orbitRx = Math.min(W, H) * 0.36;
        orbitRy = orbitRx * 0.55;
        initParticles();
        initBlobs();
        initGalaxies();
    }

    function initParticles() {
        particles = [];
        for (var i = 0; i < 100; i++) {
            particles.push({
                x: Math.random() * W, y: Math.random() * H,
                vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
                r: (0.5 + Math.random() * 2.5) * dpr,
                a: 0.08 + Math.random() * 0.35,
                twinkle: Math.random() * Math.PI * 2
            });
        }
    }

    function initBlobs() {
        blobs = [
            { x: W * 0.15, y: H * 0.2, r: W * 0.28, vx: 0.12, vy: 0.08, color: 'rgba(99,102,241,0.05)' },
            { x: W * 0.75, y: H * 0.55, r: W * 0.22, vx: -0.1, vy: -0.06, color: 'rgba(6,182,212,0.04)' },
            { x: W * 0.5, y: H * 0.85, r: W * 0.2, vx: 0.06, vy: -0.12, color: 'rgba(139,92,246,0.04)' },
            { x: W * 0.85, y: H * 0.15, r: W * 0.15, vx: -0.08, vy: 0.1, color: 'rgba(236,72,153,0.03)' }
        ];
    }

    function initGalaxies() {
        galaxies = [];
        var count = Math.max(3, Math.floor(W * H / 300000));
        for (var i = 0; i < count; i++) {
            galaxies.push({
                x: Math.random() * W, y: Math.random() * H,
                r: (15 + Math.random() * 30) * dpr,
                rot: Math.random() * Math.PI * 2,
                rotSpeed: (Math.random() - 0.5) * 0.003,
                arms: 2 + Math.floor(Math.random() * 2),
                color: ['rgba(99,102,241,', 'rgba(6,182,212,', 'rgba(139,92,246,', 'rgba(236,72,153,'][Math.floor(Math.random() * 4)],
                a: 0.06 + Math.random() * 0.08
            });
        }
    }

    function spawnShootingStar() {
        if (shootingStars.length > 3) return;
        var edge = Math.random();
        var sx, sy, angle;
        if (edge < 0.5) { sx = Math.random() * W; sy = -10; angle = Math.PI * 0.3 + Math.random() * 0.4; }
        else { sx = W + 10; sy = Math.random() * H * 0.5; angle = Math.PI * 0.6 + Math.random() * 0.3; }
        var speed = (3 + Math.random() * 4) * dpr;
        shootingStars.push({
            x: sx, y: sy,
            vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
            life: 1, decay: 0.008 + Math.random() * 0.008,
            len: (30 + Math.random() * 50) * dpr
        });
    }

    function initPulses() {
        pulses = [];
        for (var i = 0; i < N; i++) {
            pulses.push({ nodeIdx: i, t: Math.random(), speed: 0.003 + Math.random() * 0.004, dir: 1 });
            if (i % 3 === 0) pulses.push({ nodeIdx: i, nextIdx: (i + 1) % N, t: Math.random(), speed: 0.002 + Math.random() * 0.003, dir: 1, isRing: true });
        }
    }

    function getNodePos(idx, t) {
        var a = agents[idx];
        var angle = a.angle + t * 0.15;
        var ep = Math.min(entranceProgress, 1);
        var r = ep;
        var nx = cx + Math.cos(angle) * orbitRx * r;
        var ny = cy + Math.sin(angle) * orbitRy * r;
        return { x: nx, y: ny };
    }

    function drawAuroraBackground() {
        for (var i = 0; i < blobs.length; i++) {
            var b = blobs[i];
            b.x += b.vx;
            b.y += b.vy;
            if (b.x < -b.r || b.x > W + b.r) b.vx *= -1;
            if (b.y < -b.r || b.y > H + b.r) b.vy *= -1;
            var grad = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
            grad.addColorStop(0, b.color);
            grad.addColorStop(1, 'transparent');
            ctx.fillStyle = grad;
            ctx.fillRect(b.x - b.r, b.y - b.r, b.r * 2, b.r * 2);
        }
    }

    function drawParticles() {
        for (var i = 0; i < particles.length; i++) {
            var p = particles[i];
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
            if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;
            p.twinkle += 0.02 + i * 0.001;
            var ta = p.a * (0.5 + 0.5 * Math.sin(p.twinkle));
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = isDark ? 'rgba(200,200,255,' + ta + ')' : 'rgba(99,102,241,' + ta * 0.6 + ')';
            ctx.fill();
        }
    }

    function drawGalaxies() {
        for (var i = 0; i < galaxies.length; i++) {
            var g = galaxies[i];
            g.rot += g.rotSpeed;
            ctx.save();
            ctx.translate(g.x, g.y);
            ctx.rotate(g.rot);
            ctx.globalAlpha = g.a * Math.min(entranceProgress, 1);
            var grad = ctx.createRadialGradient(0, 0, 0, 0, 0, g.r);
            grad.addColorStop(0, g.color + '0.15)');
            grad.addColorStop(0.4, g.color + '0.06)');
            grad.addColorStop(1, g.color + '0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(0, 0, g.r, 0, Math.PI * 2);
            ctx.fill();
            for (var a = 0; a < g.arms; a++) {
                var armAngle = (a / g.arms) * Math.PI * 2;
                ctx.beginPath();
                for (var t = 0; t < 1; t += 0.05) {
                    var spiralR = g.r * t;
                    var spiralA = armAngle + t * 2.5;
                    var sx = Math.cos(spiralA) * spiralR;
                    var sy = Math.sin(spiralA) * spiralR;
                    if (t === 0) ctx.moveTo(sx, sy);
                    else ctx.lineTo(sx, sy);
                }
                ctx.strokeStyle = g.color + (0.12 * (1 - 0)) + ')';
                ctx.lineWidth = 1.5 * dpr;
                ctx.stroke();
            }
            ctx.globalAlpha = 1;
            ctx.restore();
        }
    }

    function drawShootingStars() {
        if (Math.random() < 0.008) spawnShootingStar();
        for (var i = shootingStars.length - 1; i >= 0; i--) {
            var s = shootingStars[i];
            s.x += s.vx; s.y += s.vy;
            s.life -= s.decay;
            if (s.life <= 0) { shootingStars.splice(i, 1); continue; }
            var tailX = s.x - (s.vx / Math.sqrt(s.vx * s.vx + s.vy * s.vy)) * s.len * s.life;
            var tailY = s.y - (s.vy / Math.sqrt(s.vx * s.vx + s.vy * s.vy)) * s.len * s.life;
            var grad = ctx.createLinearGradient(s.x, s.y, tailX, tailY);
            grad.addColorStop(0, 'rgba(255,255,255,' + s.life * 0.9 + ')');
            grad.addColorStop(1, 'rgba(99,102,241,0)');
            ctx.beginPath();
            ctx.moveTo(tailX, tailY);
            ctx.lineTo(s.x, s.y);
            ctx.strokeStyle = grad;
            ctx.lineWidth = 1.5 * dpr;
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(s.x, s.y, 2 * dpr, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,' + s.life * 0.8 + ')';
            ctx.fill();
        }
    }

    function drawOrbitEllipse() {
        var ep = Math.min(entranceProgress, 1);
        ctx.save();
        ctx.translate(cx, cy);
        ctx.scale(1, orbitRy / orbitRx);
        var grad = ctx.createLinearGradient(-orbitRx, 0, orbitRx, 0);
        grad.addColorStop(0, 'rgba(99,102,241,0.15)');
        grad.addColorStop(0.5, 'rgba(6,182,212,0.2)');
        grad.addColorStop(1, 'rgba(139,92,246,0.15)');
        ctx.strokeStyle = grad;
        ctx.lineWidth = 2.5 * dpr;
        ctx.setLineDash([8 * dpr, 6 * dpr]);
        ctx.lineDashOffset = -time * 20;
        ctx.globalAlpha = ep * 0.6;
        ctx.beginPath();
        ctx.arc(0, 0, orbitRx * ep, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.restore();
    }

    function drawBezierConnections(t) {
        var ep = Math.min(entranceProgress, 1);
        if (ep < 0.3) return;
        var connAlpha = Math.min((ep - 0.3) / 0.4, 1);
        for (var i = 0; i < N; i++) {
            var p1 = getNodePos(i, t);
            var cpx = cx + (p1.x - cx) * 0.3;
            var cpy = cy + (p1.y - cy) * 0.3;
            var isHovered = hoveredNode === i;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.quadraticCurveTo(cpx, cpy, p1.x, p1.y);
            ctx.strokeStyle = isHovered ? agents[i].color : (isDark ? 'rgba(150,150,255,' + 0.12 * connAlpha + ')' : 'rgba(99,102,241,' + 0.1 * connAlpha + ')');
            ctx.lineWidth = (isHovered ? 2.5 : 1.2) * dpr;
            ctx.stroke();
        }
    }

    function drawPulses(t) {
        var ep = Math.min(entranceProgress, 1);
        if (ep < 0.5) return;
        var pAlpha = Math.min((ep - 0.5) / 0.3, 1);
        for (var i = 0; i < pulses.length; i++) {
            var p = pulses[i];
            p.t += p.speed * p.dir;
            if (p.t > 1 || p.t < 0) { p.dir *= -1; p.t = Math.max(0, Math.min(1, p.t)); }
            var x, y;
            if (p.isRing) {
                var p1 = getNodePos(p.nodeIdx, t);
                var p2 = getNodePos(p.nextIdx, t);
                x = p1.x + (p2.x - p1.x) * p.t;
                y = p1.y + (p2.y - p1.y) * p.t;
            } else {
                var np = getNodePos(p.nodeIdx, t);
                x = cx + (np.x - cx) * p.t;
                y = cy + (np.y - cy) * p.t;
            }
            ctx.beginPath();
            ctx.arc(x, y, 2.5 * dpr, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,' + 0.8 * pAlpha + ')';
            ctx.shadowColor = '#6366f1';
            ctx.shadowBlur = 8 * dpr;
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }

    function drawCenterNode() {
        var ep = Math.min(entranceProgress, 1);
        var pulse = 1 + Math.sin(time * 2) * 0.08;
        var r = 28 * dpr * ep * pulse;
        var glowR = 50 * dpr * ep * pulse;
        var grad = ctx.createRadialGradient(cx, cy, r * 0.2, cx, cy, glowR);
        grad.addColorStop(0, 'rgba(99,102,241,0.35)');
        grad.addColorStop(0.5, 'rgba(139,92,246,0.12)');
        grad.addColorStop(1, 'rgba(99,102,241,0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, glowR, 0, Math.PI * 2);
        ctx.fill();
        var innerGrad = ctx.createRadialGradient(cx - 4 * dpr, cy - 4 * dpr, 0, cx, cy, r);
        innerGrad.addColorStop(0, '#818cf8');
        innerGrad.addColorStop(1, '#6366f1');
        ctx.fillStyle = innerGrad;
        ctx.shadowColor = '#6366f1';
        ctx.shadowBlur = 25 * dpr;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.fillStyle = '#fff';
        ctx.font = 'bold ' + (10 * dpr) + 'px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Combo', cx, cy - 6 * dpr);
        ctx.fillText('AI', cx, cy + 7 * dpr);
    }

    function drawAgentNodes(t) {
        var ep = Math.min(entranceProgress, 1);
        if (ep < 0.2) return;
        var nodeAlpha = Math.min((ep - 0.2) / 0.4, 1);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (var i = 0; i < N; i++) {
            var a = agents[i];
            var pos = getNodePos(i, t);
            var isHovered = hoveredNode === i;
            var pulse = 1 + Math.sin(time * 1.5 + i) * 0.06;
            var r = (isHovered ? 18 : 14) * dpr * nodeAlpha * pulse;
            var glowR = r * 2.2;
            ctx.globalAlpha = nodeAlpha;
            var gGrad = ctx.createRadialGradient(pos.x, pos.y, r * 0.3, pos.x, pos.y, glowR);
            gGrad.addColorStop(0, a.color + '40');
            gGrad.addColorStop(1, a.color + '00');
            ctx.fillStyle = gGrad;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, glowR, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowColor = a.color;
            ctx.shadowBlur = 15 * dpr;
            ctx.fillStyle = a.color;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;
            ctx.fillStyle = '#fff';
            ctx.font = 'bold ' + (8 * dpr) + 'px Inter, sans-serif';
            ctx.fillText(a.label.charAt(0), pos.x, pos.y);
            var labelY = pos.y + r + 14 * dpr;
            ctx.font = '600 ' + (11 * dpr) + 'px Inter, sans-serif';
            var tw = ctx.measureText(a.label).width;
            var px = 6 * dpr, py = 3 * dpr;
            ctx.fillStyle = isDark ? 'rgba(15,15,30,0.75)' : 'rgba(255,255,255,0.85)';
            ctx.beginPath();
            ctx.roundRect(pos.x - tw / 2 - px, labelY - 8 * dpr - py, tw + px * 2, 16 * dpr + py * 2, 6 * dpr);
            ctx.fill();
            ctx.fillStyle = a.color;
            ctx.fillText(a.label, pos.x, labelY);
            ctx.globalAlpha = 1;
            a._screenX = pos.x / dpr;
            a._screenY = pos.y / dpr;
            a._screenR = r / dpr;
        }
    }

    function handleMouse(e) {
        var rect = canvas.getBoundingClientRect();
        mouseX = (e.clientX - rect.left) / rect.width;
        mouseY = (e.clientY - rect.top) / rect.height;
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;
        var found = -1;
        for (var i = 0; i < N; i++) {
            var a = agents[i];
            if (!a._screenX) continue;
            var dx = mx - a._screenX, dy = my - a._screenY;
            if (Math.sqrt(dx * dx + dy * dy) < a._screenR + 10) { found = i; break; }
        }
        hoveredNode = found >= 0 ? found : null;
        if (hoveredNode !== null && tooltip) {
            var ag = agents[hoveredNode];
            tooltip.innerHTML = '<strong>' + ag.label + '</strong><br>' + ag.desc;
            tooltip.style.left = (ag._screenX + 20) + 'px';
            tooltip.style.top = (ag._screenY - 20) + 'px';
            tooltip.classList.add('visible');
        } else if (tooltip) {
            tooltip.classList.remove('visible');
        }
        canvas.style.cursor = hoveredNode !== null ? 'pointer' : 'default';
    }

    canvas.addEventListener('mousemove', handleMouse);
    canvas.addEventListener('mouseleave', function() {
        mouseX = 0.5; mouseY = 0.5; hoveredNode = null;
        if (tooltip) tooltip.classList.remove('visible');
        canvas.style.cursor = 'default';
    });

    var observer = new MutationObserver(function() {
        isDark = document.body.classList.contains('dark-mode');
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });

    resize();
    initPulses();
    window.addEventListener('resize', resize);

    var visObs = new IntersectionObserver(function(entries) {
        running = entries[0].isIntersecting;
    }, { threshold: 0.05 });
    visObs.observe(canvas);

    function frame() {
        if (!running) { requestAnimationFrame(frame); return; }
        time += 0.016;
        if (entranceProgress < 1.2) entranceProgress += 0.012;
        tiltX += ((mouseY - 0.5) * 6 - tiltX) * 0.05;
        tiltY += ((mouseX - 0.5) * -6 - tiltY) * 0.05;
        heroVisual.style.transform = 'rotateX(' + tiltX + 'deg) rotateY(' + tiltY + 'deg)';
        ctx.clearRect(0, 0, W, H);
        drawAuroraBackground();
        drawGalaxies();
        drawParticles();
        drawShootingStars();
        drawOrbitEllipse();
        drawBezierConnections(time);
        drawPulses(time);
        drawCenterNode();
        drawAgentNodes(time);
        requestAnimationFrame(frame);
    }
    frame();
}

function initScrollProgress() {
    var bar = document.getElementById('scroll-progress');
    if (!bar) return;
    window.addEventListener('scroll', function() {
        var h = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.width = h > 0 ? (window.scrollY / h * 100) + '%' : '0%';
    });
}

function initTestimonials() {
    var cards = document.querySelectorAll('.testimonial-card');
    var dots = document.querySelectorAll('.t-dot');
    if (!cards.length) return;
    var current = 0;
    var timer;
    function show(i) {
        cards.forEach(function(c) { c.classList.remove('active'); });
        dots.forEach(function(d) { d.classList.remove('active'); });
        cards[i].classList.add('active');
        dots[i].classList.add('active');
        current = i;
    }
    function next() { show((current + 1) % cards.length); }
    function prev() { show((current - 1 + cards.length) % cards.length); }
    function startAuto() { timer = setInterval(next, 5000); }
    dots.forEach(function(d) {
        d.addEventListener('click', function() {
            clearInterval(timer);
            show(parseInt(d.dataset.index));
            startAuto();
        });
    });
    var prevBtn = document.getElementById('t-prev');
    var nextBtn = document.getElementById('t-next');
    if (prevBtn) prevBtn.addEventListener('click', function() { clearInterval(timer); prev(); startAuto(); });
    if (nextBtn) nextBtn.addEventListener('click', function() { clearInterval(timer); next(); startAuto(); });
    startAuto();
}

function initFAQ() {
    document.querySelectorAll('.faq-question').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var item = btn.closest('.faq-item');
            var wasOpen = item.classList.contains('open');
            document.querySelectorAll('.faq-item').forEach(function(fi) { fi.classList.remove('open'); });
            if (!wasOpen) item.classList.add('open');
        });
    });
}

function initPaymentIcons() {
    var overlay = document.getElementById('payment-popup-overlay');
    var title = document.getElementById('payment-popup-title');
    var closeBtn = document.getElementById('payment-popup-close');
    if (!overlay) return;
    document.querySelectorAll('.payment-icon').forEach(function(btn) {
        btn.addEventListener('click', function() {
            title.textContent = 'Payment via ' + btn.dataset.method;
            overlay.classList.add('open');
        });
    });
    closeBtn.addEventListener('click', function() { overlay.classList.remove('open'); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.classList.remove('open'); });
}

function initScrollReveal() {
    var els = document.querySelectorAll('.section-header, .service-card, .benefit-card, .research-area, .stat, .contact-info, .contact-form, .faq-item, .testimonial-card');
    els.forEach(function(el) { el.classList.add('reveal'); });
    var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    els.forEach(function(el) { observer.observe(el); });
}

function initAuth() {
    const authBtn = document.getElementById('auth-btn');
    const userMenu = document.getElementById('user-menu');
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userDropdown = document.getElementById('user-dropdown');
    const userDisplayName = document.getElementById('user-display-name');
    const authOverlay = document.getElementById('auth-overlay');
    const authModalClose = document.getElementById('auth-modal-close');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const loginError = document.getElementById('login-error');
    const registerError = document.getElementById('register-error');
    const dashOverlay = document.getElementById('dashboard-overlay');
    const dashClose = document.getElementById('dashboard-close');
    const dashUserInfo = document.getElementById('dashboard-user-info');
    const dashLogout = document.getElementById('dashboard-logout');
    const dashMsgForm = document.getElementById('dash-message-form');
    const dashMsgInput = document.getElementById('dash-message-input');
    const dashMsgList = document.getElementById('dash-messages-list');
    const dashNotesText = document.getElementById('dash-notes-text');
    const dashNotesSave = document.getElementById('dash-notes-save');
    const dashOrdersList = document.getElementById('dash-orders-list');

    if (!authBtn) return;

    let authToken = localStorage.getItem('auth_token') || '';
    let currentUser = null;

    function authHeaders() {
        return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken };
    }

    function setLoggedIn(user, token) {
        authToken = token;
        currentUser = user;
        localStorage.setItem('auth_token', token);
        authBtn.style.display = 'none';
        userMenu.style.display = '';
        userDisplayName.textContent = user.name.split(' ')[0];
    }

    function setLoggedOut() {
        authToken = '';
        currentUser = null;
        localStorage.removeItem('auth_token');
        authBtn.style.display = '';
        userMenu.style.display = 'none';
        userDropdown.classList.remove('open');
        dashOverlay.classList.remove('open');
    }

    function openAuthModal(tab) {
        authOverlay.classList.add('open');
        loginError.textContent = '';
        registerError.textContent = '';
        document.querySelectorAll('.auth-tab').forEach(function(t) {
            t.classList.toggle('active', t.dataset.tab === tab);
        });
        loginForm.style.display = tab === 'login' ? '' : 'none';
        registerForm.style.display = tab === 'register' ? '' : 'none';
    }

    function closeAuthModal() { authOverlay.classList.remove('open'); }

    if (authToken) {
        fetch('/api/auth/me', { headers: authHeaders() })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.id) setLoggedIn(data, authToken);
                else setLoggedOut();
            })
            .catch(function() { setLoggedOut(); });
    }

    authBtn.addEventListener('click', function() { openAuthModal('login'); });
    authModalClose.addEventListener('click', closeAuthModal);
    authOverlay.addEventListener('click', function(e) { if (e.target === authOverlay) closeAuthModal(); });

    document.querySelectorAll('.auth-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            openAuthModal(tab.dataset.tab);
        });
    });

    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        loginError.textContent = '';
        var email = document.getElementById('login-email').value;
        var password = document.getElementById('login-password').value;
        var btn = loginForm.querySelector('.auth-submit');
        btn.disabled = true;
        fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            if (!res.ok) { loginError.textContent = res.data.error || 'Login failed.'; return; }
            setLoggedIn(res.data.user, res.data.token);
            closeAuthModal();
            loginForm.reset();
        })
        .catch(function() { btn.disabled = false; loginError.textContent = 'Network error.'; });
    });

    registerForm.addEventListener('submit', function(e) {
        e.preventDefault();
        registerError.textContent = '';
        var name = document.getElementById('reg-name').value;
        var email = document.getElementById('reg-email').value;
        var pw = document.getElementById('reg-password').value;
        var pw2 = document.getElementById('reg-password2').value;
        if (pw !== pw2) { registerError.textContent = 'Passwords do not match.'; return; }
        var btn = registerForm.querySelector('.auth-submit');
        btn.disabled = true;
        fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, email: email, password: pw })
        })
        .then(function(r) { return r.json().then(function(d) { return { ok: r.ok, data: d }; }); })
        .then(function(res) {
            btn.disabled = false;
            if (!res.ok) { registerError.textContent = res.data.error || 'Registration failed.'; return; }
            setLoggedIn(res.data.user, res.data.token);
            closeAuthModal();
            registerForm.reset();
        })
        .catch(function() { btn.disabled = false; registerError.textContent = 'Network error.'; });
    });

    userMenuToggle.addEventListener('click', function() {
        userDropdown.classList.toggle('open');
    });
    document.addEventListener('click', function(e) {
        if (!userMenu.contains(e.target)) userDropdown.classList.remove('open');
    });

    function doLogout() {
        fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() }).catch(function() {});
        setLoggedOut();
    }

    document.getElementById('user-logout-link').addEventListener('click', function(e) {
        e.preventDefault();
        doLogout();
    });
    dashLogout.addEventListener('click', doLogout);

    function formatTime(ts) {
        var d = new Date(ts * 1000);
        return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function renderMessages(messages) {
        if (!messages.length) {
            dashMsgList.innerHTML = '<div class="dash-empty">No messages yet. Send one below!</div>';
            return;
        }
        dashMsgList.innerHTML = messages.map(function(m) {
            return '<div class="dash-msg ' + m.sender + '">' +
                '<div>' + m.text.replace(/</g, '&lt;') + '</div>' +
                '<div class="dash-msg-time">' + formatTime(m.created_at) + '</div>' +
            '</div>';
        }).join('');
        dashMsgList.scrollTop = dashMsgList.scrollHeight;
    }

    function loadMessages() {
        fetch('/api/user/messages', { headers: authHeaders() })
            .then(function(r) { return r.json(); })
            .then(function(data) { if (data.messages) renderMessages(data.messages); })
            .catch(function() {});
    }

    function loadNotes() {
        fetch('/api/user/notes', { headers: authHeaders() })
            .then(function(r) { return r.json(); })
            .then(function(data) { dashNotesText.value = data.text || ''; })
            .catch(function() {});
    }

    function renderOrders() {
        var orders = [
            { name: 'AI Chatbot Setup', date: '2025-10-15', status: 'completed' },
            { name: 'Data Pipeline Integration', date: '2025-11-02', status: 'active' },
            { name: 'Custom LLM Fine-tuning', date: '2025-11-20', status: 'pending' },
        ];
        dashOrdersList.innerHTML = orders.map(function(o) {
            return '<div class="dash-order-item">' +
                '<div><div class="dash-order-name">' + o.name + '</div>' +
                '<div class="dash-order-date">' + o.date + '</div></div>' +
                '<span class="dash-order-status ' + o.status + '">' + o.status.charAt(0).toUpperCase() + o.status.slice(1) + '</span>' +
            '</div>';
        }).join('');
    }

    function openDashboard() {
        if (!currentUser) return;
        userDropdown.classList.remove('open');
        dashOverlay.classList.add('open');
        dashUserInfo.innerHTML = '<strong>' + currentUser.name + '</strong> &mdash; ' + currentUser.email;
        loadMessages();
        loadNotes();
        renderOrders();
    }

    document.getElementById('user-dashboard-link').addEventListener('click', function(e) {
        e.preventDefault();
        openDashboard();
    });
    dashClose.addEventListener('click', function() { dashOverlay.classList.remove('open'); });
    dashOverlay.addEventListener('click', function(e) { if (e.target === dashOverlay) dashOverlay.classList.remove('open'); });

    document.querySelectorAll('.dash-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.dash-tab').forEach(function(t) { t.classList.remove('active'); });
            document.querySelectorAll('.dash-section').forEach(function(s) { s.classList.remove('active'); });
            tab.classList.add('active');
            document.getElementById('dash-' + tab.dataset.dtab).classList.add('active');
        });
    });

    dashMsgForm.addEventListener('submit', function(e) {
        e.preventDefault();
        var text = dashMsgInput.value.trim();
        if (!text) return;
        dashMsgInput.value = '';
        fetch('/api/user/messages', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ text: text })
        })
        .then(function() { loadMessages(); })
        .catch(function() {});
    });

    dashNotesSave.addEventListener('click', function() {
        fetch('/api/user/notes', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ text: dashNotesText.value })
        })
        .then(function(r) { return r.json(); })
        .then(function() {
            dashNotesSave.textContent = 'Saved!';
            setTimeout(function() { dashNotesSave.innerHTML = '<i class="fas fa-save"></i> Save Notes'; }, 1500);
        })
        .catch(function() {});
    });
}

window.addEventListener('error', function(e) {
    if (e.target.tagName === 'LINK' || e.target.tagName === 'SCRIPT') {
        console.warn('Failed to load external resource:', e.target.src || e.target.href);
    }
}, true);
