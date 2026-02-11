// Security Page Interactivity

document.addEventListener('DOMContentLoaded', function() {
    // Add smooth scroll behavior
    setupInteractivity();
    loadAnalytics();
});

function setupInteractivity() {
    // Add click handlers for category cards
    const categoryCards = document.querySelectorAll('.category-card');
    
    categoryCards.forEach((card, index) => {
        card.addEventListener('mouseenter', function() {
            this.style.zIndex = 10;
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.zIndex = 'auto';
        });
    });

    // Add action item click feedback
    const actionItems = document.querySelectorAll('.action-item');
    actionItems.forEach(item => {
        item.style.cursor = 'pointer';
        item.addEventListener('click', function() {
            this.style.transform = 'scale(0.98)';
            setTimeout(() => {
                this.style.transform = 'translateX(5px)';
            }, 100);
        });
    });
}

function loadAnalytics() {
    // This function can be extended to fetch actual security data
    console.log('📊 Security Monitoring Dashboard Loaded');
    console.log('🛡️ Threat Categories: 6');
    console.log('⚡ Quick Reference: Available');
    console.log('💡 Best Practices: Loaded');
}

// Make category cards expandable with enhanced visuals
function enhanceCategoryCards() {
    const cards = document.querySelectorAll('.category-card');
    
    cards.forEach((card) => {
        card.addEventListener('click', function() {
            const content = this.querySelector('.category-content');
            
            // Smooth height animation
            if (content.style.maxHeight === '' || content.style.maxHeight === '0px') {
                content.style.transition = 'max-height 0.3s ease';
                content.style.maxHeight = '500px';
            }
        });
    });
}

// Print-friendly security guide
function printSecurityGuide() {
    window.print();
}

// Export threat assessment
function exportThreatAssessment() {
    const threatData = {
        timestamp: new Date().toISOString(),
        categories: 6,
        threats: [
            'Suspicious Child Processes',
            'Privilege Escalation',
            'Network Anomalies',
            'Process Injection & DLL Hijacking',
            'Protected Directory Access',
            'Memory Exploit Patterns'
        ]
    };
    
    const dataStr = JSON.stringify(threatData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `security-assessment-${new Date().getTime()}.json`;
    link.click();
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl+P to print
    if (event.ctrlKey && event.key === 'p') {
        event.preventDefault();
        printSecurityGuide();
    }
    
    // Ctrl+E to export
    if (event.ctrlKey && event.key === 'e') {
        event.preventDefault();
        exportThreatAssessment();
    }
});

// Scroll to top functionality
function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Add scroll-to-top button visibility
window.addEventListener('scroll', function() {
    const scrollButton = document.querySelector('.scroll-to-top');
    if (scrollButton) {
        if (window.pageYOffset > 300) {
            scrollButton.style.opacity = '1';
            scrollButton.style.pointerEvents = 'auto';
        } else {
            scrollButton.style.opacity = '0';
            scrollButton.style.pointerEvents = 'none';
        }
    }
});
