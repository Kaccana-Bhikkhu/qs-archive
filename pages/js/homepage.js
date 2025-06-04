// homepage.js scripts the pages homepage.html and search/Featured.html
// Both pages rely on ./assets/Homepage.json

import {configureLinks, openLocalPage, framePage} from './frame.js';

const DEBUG = false;

let gHomepageDatabase = null; // The global database, loaded from assets/HomepageDatabase.json
let gNavBar = null; // The main navigation bar, set after all DOM content loaded

let todaysExcerpt = 0; // the featured excerpt currently displayed on the homepage
let gCurrentExcerpt = 0; // The featured excerpt currently displayed on search/Featured.html

function initializeTodaysExcerpt() {
    // Calculate which featured excerpt to display based on today's date

    todaysExcerpt = 0;
    gCurrentExcerpt = todaysExcerpt;
}

function displayFeaturedExcerpt() {
    // Display the html code for current featured excerpt

    let excerptCount = gHomepageDatabase.excerpts.length;
    let excerptToDisplay = ((gCurrentExcerpt % excerptCount) + excerptCount) % excerptCount

    let displayArea = document.getElementById("random-excerpt");
    displayArea.innerHTML = gHomepageDatabase.excerpts[excerptToDisplay].html;
    configureLinks(displayArea,"indexes/homepage.html");

    let titleArea = document.getElementById("page-title");
    let title = "Today's featured excerpt:"
    if (gCurrentExcerpt > 0)
        title = `Random excerpt (${gCurrentExcerpt}):`;
    else if (gCurrentExcerpt < 0) {
        let pastDate = new Date();
        pastDate.setDate(pastDate.getDate() + gCurrentExcerpt);
        title = `Excerpt featured on ${pastDate.toDateString()}:`;
    }

    titleArea.innerHTML = title;
}

function displayNextFeaturedExcerpt(increment) {
    // display the next or previous (increment = -1) random excerpt
    gCurrentExcerpt += increment;

    displayFeaturedExcerpt();
}

// Homepage date display
function updateDate() {
    const dateElement = document.getElementById('currentDate');
    if (dateElement) {
        const formattedDate = new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        dateElement.textContent = formattedDate;
    }
}

// Utility Functions
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Meditation Timer
class MeditationTimer {
    constructor() {
        this.duration = 5;
        this.timeLeft = this.duration * 60;
        this.isActive = false;
        this.interval = null;
        this.bell = new Audio('assets/sounds/meditation-bell.mp3');
        
        // DOM Elements
        this.timeDisplay = document.getElementById('timeDisplay');
        this.playButton = document.getElementById('timerPlayButton');
        this.resetButton = document.getElementById('resetButton');
        this.durationSlider = document.getElementById('durationSlider');
        this.durationDisplay = document.getElementById('durationDisplay');

        this.initializeListeners();
    }

    initializeListeners() {
        this.playButton.addEventListener('click', () => this.toggleTimer());
        this.resetButton.addEventListener('click', () => this.resetTimer());
        this.durationSlider.addEventListener('input', (e) => this.updateDuration(e));
    }

    toggleTimer() {
        this.isActive = !this.isActive;
        const playButtonIcon = this.playButton.querySelector('img');
        playButtonIcon.src = this.isActive ? 
            'images/icons/pause.svg' : 
            'images/icons/play.svg';

        if (this.isActive) {
            this.startTimer();
        } else {
            this.pauseTimer();
        }
    }

    startTimer() {
        this.interval = setInterval(() => {
            this.timeLeft--;
            this.updateDisplay();
            
            if (this.timeLeft === 0) {
                this.handleTimerComplete();
            }
        }, 1000);
    }

    pauseTimer() {
        clearInterval(this.interval);
    }

    resetTimer() {
        this.isActive = false;
        clearInterval(this.interval);
        this.timeLeft = this.duration * 60;
        
        // Update the play button icon to show play
        const playButtonIcon = this.playButton.querySelector('img');
        playButtonIcon.src = 'images/icons/play.svg';
        
        this.updateDisplay();
    }

    updateDuration(event) {
        this.duration = parseInt(event.target.value);
        this.durationDisplay.textContent = this.duration;
        if (!this.isActive) {
            this.timeLeft = this.duration * 60;
            this.updateDisplay();
        }
    }

    updateDisplay() {
        this.timeDisplay.textContent = formatTime(this.timeLeft);
    }

    handleTimerComplete() {
        this.isActive = false;
        this.resetTimer();
        this.bell.play().catch(error => console.log('Error playing bell:', error));
    }
}

function highlightNavMenuItem() {
    // Highlight items in the main nav menu if the appropriate page is loaded

    const pagesWithin = { // regex matches to highlight each menu item
        "Home": /^homepage/,
        "Key Topics ▾": /^topics|^cluster/,
        "Tags ▾": /^tags|^drilldown|^dispatch\/Tags/,
        "Events ▾": /^events|^dispatch\/Events/,
        "About": /^about/
    }

    let openPage = framePage();
    debugLog("Currently open:",openPage);
    for (let item of gNavBar.querySelector(".main-nav").querySelectorAll("li")) {
        if (pagesWithin[item.querySelector("a").textContent].test(openPage))
            item.classList.add("highlighted")
        else
            item.classList.remove("highlighted");
    }
}

function configurePopupMenus(loadedFrame) {
    // Set triggers for select.sublink-dropdown items on the page

    for (let menu of loadedFrame.querySelectorAll("select.sublink-dropdown")) {
        menu.addEventListener("change",function (event) {
            openLocalPage(event.target.value);
            debugLog("Selection changed to",event.target.value);
        })
    }
}

export async function loadHomepage(loadedFrame) {
    // Called every time a page is loaded.
    // Load gHomepageDatabase and wire the needed elements

    dropdownMenuClick(null); // Close all dropdown menus
    gNavBar.querySelector('.main-nav').classList.remove("active");

    if (!gHomepageDatabase) {
        await fetch('./assets/HomepageDatabase.json')
        .then((response) => response.json())
        .then((json) => {
            gHomepageDatabase = json; 
            debugLog("Loaded homepage database.");
        });
        initializeTodaysExcerpt()
    }

    highlightNavMenuItem();
    configurePopupMenus(loadedFrame);

    // This code runs only for search/Featured.html
    let prevButton = document.getElementById("random-prev");
    let nextButton = document.getElementById("random-next");
    if (prevButton || nextButton) {
        prevButton.onclick = () => { displayNextFeaturedExcerpt(-1); };
        nextButton.onclick = () => { displayNextFeaturedExcerpt(1); };
        displayNextFeaturedExcerpt(0);
    }

    // This code runs only for homepage.html
    let featuredExcerptContainer = document.getElementById("todays-excerpt");
    if (featuredExcerptContainer) {
        featuredExcerptContainer.innerHTML = gHomepageDatabase.excerpts[todaysExcerpt].shortHtml;
        configureLinks(featuredExcerptContainer,"index.html");
        
        updateDate();
        new MeditationTimer();
    }
}

function dropdownMenuClick(clickedItem) {
    // Toggle the menu item clicked (a div.dropdown element)
    // Close all other menus; clickedItem == null closes all menus.
    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        if (dropdownMenu === clickedItem)
            dropdownMenu.classList.toggle('menu-open');
        else
            dropdownMenu.classList.remove('menu-open');
    });

    // The same for the floating search bar
    if (clickedItem === document.getElementById('nav-search-icon')) {
        let searchBar = gNavBar.querySelector('.floating-search');
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active'))
            document.getElementById('floating-search-input').focus();
    } else
        gNavBar.querySelector('.floating-search').classList.remove('active');
    
    // and the Abhayagiri nav menu
    if (clickedItem === document.getElementById('nav-abhayagiri-icon')) {
        document.querySelector('.abhayagiri-grid-menu').classList.toggle('active');
    } else
        document.querySelector('.abhayagiri-grid-menu').classList.remove('active');
}

function setupNavMenuTriggers() {
    // Configure javascript triggers for header elements
    gNavBar = document.querySelector('.header-content');

    // Clicking on the hamburger icon toggles the main nav menu
    gNavBar.querySelector('.hamburger').addEventListener('click', function() {
        gNavBar.querySelector('.main-nav').classList.toggle('active');
        dropdownMenuClick(null); // Close all dropdown menus
    });

    // Close the dropdown menus and the main nav menu on a menu click
    gNavBar.querySelectorAll('.dropdown-content > a').forEach(function(dropdownTrigger) {
        dropdownTrigger.addEventListener('click', function() {
            this.parentElement.style.display = "none";
            gNavBar.querySelector('.main-nav').classList.remove("active");
            dropdownMenuClick(null);
        });
    });

    // Close the dropdown menus when the user clicks anywhere else
    document.addEventListener('click',function(event) {
        if (!event.target.matches('.keep-nav-menu-open, .keep-nav-menu-open *')) {
            dropdownMenuClick(null);
        }
    });

    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        dropdownMenu.querySelector(".dropdown-trigger").addEventListener('click', function() {
            dropdownMenuClick(this.parentElement);
        });
        // Re-enable hover functionality when mousing over a dropdown menu
        dropdownMenu.addEventListener('mouseenter', function() {
            this.querySelector(".dropdown-content").style.display = "";
        });
    });

    // Clicking the search button toggles the floating search bar
    document.getElementById('nav-search-icon').addEventListener('click', function() {
        dropdownMenuClick(this); // Close all dropdown menus
    });
    // Handle clicking the search button
    document.getElementById('floating-search-go').addEventListener('click', function(event) {
        let inputBox = document.getElementById('floating-search-input');
        let searchQuery = encodeURIComponent(inputBox.value);
        inputBox.value = "";
        debugLog('Search bar search for',searchQuery);
        event.preventDefault();
        openLocalPage("search/Text-search.html",`q=${searchQuery}&search=all`);
    });

    // Clicking Abhayagiri icon toggles the Abhayagiri grid menu
    document.getElementById('nav-abhayagiri-icon').addEventListener('click', function() {
        dropdownMenuClick(this);
    });

    // Keyboard shortcuts
    document.addEventListener("keydown", function(event) {
        // '/' key opens the search bar if it's not open already
        if ((event.key == "/") && !gNavBar.querySelector('.floating-search.active')) {
            event.preventDefault();
            document.getElementById("nav-search-icon").click();
        }
        // Esc key closes all menus if any are open
        if ((event.key == "Escape") && gNavBar.querySelector('.active')) {
            event.preventDefault();
            dropdownMenuClick(null);
            gNavBar.querySelector('.main-nav').classList.remove("active");
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Called only once after pages/index.html DOM is loaded
    debugLog("DOMContentLoaded event");
	configureLinks(document.querySelector("header"),"index.html");
	configureLinks(document.querySelector("footer"),"index.html");

    setupNavMenuTriggers();
});
