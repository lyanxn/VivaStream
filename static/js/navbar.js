document.addEventListener('DOMContentLoaded', () => {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    const openIcon = document.getElementById('menu-open-icon');
    const closeIcon = document.getElementById('menu-close-icon');
    const searchInput = document.getElementById('search-input-desktop');
    const searchResults = document.getElementById('search-results');

    if (mobileMenuButton) {
        mobileMenuButton.addEventListener('click', (e) => {
            e.stopPropagation();
            const isExpanded = mobileMenuButton.getAttribute('aria-expanded') === 'true';
            mobileMenuButton.setAttribute('aria-expanded', !isExpanded);
            
            if (mobileMenu) {
                mobileMenu.classList.toggle('hidden');
            }
            
            if (openIcon) openIcon.classList.toggle('hidden');
            if (closeIcon) closeIcon.classList.toggle('hidden');
        });

        document.addEventListener('click', (e) => {
            if (mobileMenu && !mobileMenu.classList.contains('hidden') && 
                !mobileMenuButton.contains(e.target) && 
                !mobileMenu.contains(e.target)) {
                mobileMenuButton.click();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && mobileMenu && !mobileMenu.classList.contains('hidden')) {
                mobileMenuButton.click();
                mobileMenuButton.focus();
            }
        });
    }

    if (searchInput && searchResults) {
        let isSearching = false;
        let closeSearchResultsTimeout = null;

        searchResults.addEventListener('htmx:beforeSwap', () => {
            isSearching = true;
            if (closeSearchResultsTimeout) {
                clearTimeout(closeSearchResultsTimeout);
                closeSearchResultsTimeout = null;
            }
        });

        searchResults.addEventListener('htmx:afterSwap', () => {
            isSearching = false;
            requestAnimationFrame(() => {
                if (searchResults.innerHTML.trim()) {
                    searchResults.classList.add('block');
                    searchResults.classList.remove('hidden');
                    
                    const resultLinks = searchResults.querySelectorAll('a');
                    resultLinks.forEach((link) => {
                        link.onclick = null;
                        
                        link.addEventListener('click', (e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            window.location.href = link.href;
                            searchResults.innerHTML = '';
                            searchResults.classList.add('hidden');
                            searchResults.classList.remove('block');
                            searchInput.value = '';
                        });
                    });
                } else {
                    searchResults.classList.add('hidden');
                    searchResults.classList.remove('block');
                }
            });
        });

        searchResults.addEventListener('htmx:responseError', (event) => {
            isSearching = false;
            console.error('HTMX search error:', event.detail);
        });

        searchInput.addEventListener('focus', (e) => {
            e.stopPropagation();
            if (searchResults && searchResults.innerHTML.trim()) {
                searchResults.classList.add('block');
                searchResults.classList.remove('hidden');
            }
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                searchResults.innerHTML = '';
                searchResults.classList.add('hidden');
                searchResults.classList.remove('block');
                searchInput.value = '';
                searchInput.blur();
            }
        });

        searchInput.addEventListener('input', (e) => {
            if (!searchInput.value.trim()) {
                searchResults.innerHTML = '';
                searchResults.classList.add('hidden');
                searchResults.classList.remove('block');
            }
        });

        searchInput.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        searchResults.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        document.addEventListener('click', (e) => {
            if (isSearching) return;
            
            const clickedSearchInput = searchInput.contains(e.target);
            const clickedSearchResults = searchResults.contains(e.target);
            
            if (!clickedSearchInput && !clickedSearchResults) {
                searchResults.classList.add('hidden');
                searchResults.classList.remove('block');
            }
        });

        searchInput.addEventListener('keydown', (e) => {
            const resultLinks = searchResults.querySelectorAll('a');
            const activeLink = searchResults.querySelector('a:focus');
            
            if (e.key === 'ArrowDown' && resultLinks.length > 0) {
                e.preventDefault();
                if (!activeLink) {
                    resultLinks[0].focus();
                } else {
                    const nextLink = activeLink.nextElementSibling;
                    if (nextLink && nextLink.tagName === 'A') {
                        nextLink.focus();
                    }
                }
            } else if (e.key === 'ArrowUp' && resultLinks.length > 0) {
                e.preventDefault();
                if (activeLink) {
                    const prevLink = activeLink.previousElementSibling;
                    if (prevLink && prevLink.tagName === 'A') {
                        prevLink.focus();
                    } else {
                        searchInput.focus();
                    }
                }
            }
        });
    }

    const userMenuButton = document.getElementById('user-menu-button');
    const userMenuButtonMobile = document.getElementById('user-menu-button-mobile');
    const userDropdownMenu = document.getElementById('user-dropdown-menu');
    const dropdownArrow = userMenuButton ? userMenuButton.querySelector('svg') : null;

    function toggleUserMenu() {
        if (!userDropdownMenu) return;
        
        const isExpanded = userMenuButton ? 
            userMenuButton.getAttribute('aria-expanded') === 'true' : 
            userMenuButtonMobile.getAttribute('aria-expanded') === 'true';
        
        const button = userMenuButton || userMenuButtonMobile;
        button.setAttribute('aria-expanded', !isExpanded);
        userDropdownMenu.classList.toggle('hidden');
        
        if (dropdownArrow) {
            if (!isExpanded) {
                dropdownArrow.style.transform = 'rotate(180deg)';
            } else {
                dropdownArrow.style.transform = 'rotate(0deg)';
            }
        }
    }

    if (userMenuButton) {
        userMenuButton.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleUserMenu();
        });
    }
    
    if (userMenuButtonMobile) {
        userMenuButtonMobile.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleUserMenu();
        });
    }

    document.addEventListener('click', (e) => {
        if (userDropdownMenu && !userDropdownMenu.classList.contains('hidden')) {
            const isClickInsideMenu = userDropdownMenu.contains(e.target);
            const isClickOnButton = (userMenuButton && userMenuButton.contains(e.target)) || 
                                   (userMenuButtonMobile && userMenuButtonMobile.contains(e.target));
            
            if (!isClickInsideMenu && !isClickOnButton) {
                toggleUserMenu();
            }
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && userDropdownMenu && !userDropdownMenu.classList.contains('hidden')) {
            toggleUserMenu();
            const button = userMenuButton || userMenuButtonMobile;
            if (button) button.focus();
        }
    });

    const navLinks = document.querySelectorAll('.navbar-nav-link');
    navLinks.forEach(link => {
        link.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                window.location.href = link.href;
            }
        });
    });
});
