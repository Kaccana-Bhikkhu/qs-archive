// homepage.js scripts the pages homepage.html and search/Featured.html
// Both pages rely on ./assets/FeaturedDatabase.json

import {configureLinks, openLocalPage, framePage} from './frame.js';
import './autoComplete.js';
import {SearchQuery,gSearchers,loadSearchDatabase} from './search.js';

const DEBUG = false;

let gFeaturedDatabase = null; // The global database, loaded from assets/FeaturedDatabase.json
let gNavBar = null; // The main navigation bar, set after all DOM content loaded

let gTodaysExcerpt = 0; // the featured excerpt currently displayed on the homepage
let gSearchFeaturedOffset = 0; // The featured excerpt currently displayed on search/Featured.html
let gRandomExcerpts = []; // The random excerpts we have generated this session.

function calendarModulus(index) {
    // Return index modulo the length of the calendar

    let excerptCount = gFeaturedDatabase.calendar.length;
    return ((index % excerptCount) + excerptCount) % excerptCount;
}

let gDebugDateOffset = 0;
function initializeTodaysExcerpt(todaysDate) {
    // Calculate which featured excerpt to display based on today's date
    // todaysDate overrides today with a different date

    if (!todaysDate)
        todaysDate = new Date();
    let calendarStartDate = new Date(gFeaturedDatabase.startDate);
    let daysSinceStart = Math.floor((todaysDate - calendarStartDate) / (1000 * 3600 * 24));
    debugLog("Days since start:",todaysDate,calendarStartDate,daysSinceStart);
    gTodaysExcerpt = calendarModulus(daysSinceStart);
    gSearchFeaturedOffset = 0;
}

function displayFeaturedExcerpt() {
    // Display the html code for current featured excerpt on search/Featured.html

    let excerptToDisplay = gFeaturedDatabase.calendar[calendarModulus(gTodaysExcerpt + gSearchFeaturedOffset)];
    
    let title = "Today's featured excerpt"
    if (gSearchFeaturedOffset > 0) {
        let excerptCodes = Object.keys(gFeaturedDatabase.excerpts);
        while (gRandomExcerpts.length < gSearchFeaturedOffset) {
            let randomIndex = Math.floor(Math.random() * excerptCodes.length);
            gRandomExcerpts.push(excerptCodes[randomIndex]);
        }
        excerptToDisplay = gRandomExcerpts[gSearchFeaturedOffset - 1];
        title = `Random excerpt (${gSearchFeaturedOffset})`;
    } else if (gSearchFeaturedOffset < 0) {
        let pastDate = new Date();
        pastDate.setDate(pastDate.getDate() + gSearchFeaturedOffset);
        let options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        title = `Excerpt featured on ${pastDate.toLocaleDateString("en-us",options)}`;
    }

    let displayArea = document.getElementById("random-excerpt");
    displayArea.innerHTML = gFeaturedDatabase.excerpts[excerptToDisplay].html;
    configureLinks(displayArea,"search/homepage.html");

    let titleArea = document.getElementById("page-title");
    titleArea.innerHTML = title;
}

function displayNextFeaturedExcerpt(increment) {
    // display the next or previous (increment = -1) random excerpt
    gSearchFeaturedOffset += increment;

    displayFeaturedExcerpt();
}

// Homepage date display
function updateDate(theDate) {
    const dateElement = document.getElementById('currentDate');
    if (dateElement) {
        if (!theDate)
            theDate = new Date();
        const formattedDate = theDate.toLocaleDateString('en-US', {
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
        
        this.reloadPage();
    }

    reloadPage() {
        // DOM elements must be updated each time we reload the main page
        this.timeDisplay = document.getElementById('timeDisplay');
        this.playButton = document.getElementById('timerPlayButton');
        this.resetButton = document.getElementById('resetButton');
        this.durationSlider = document.getElementById('durationSlider');
        this.durationDisplay = document.getElementById('durationDisplay');

        this.playButton.addEventListener('click', () => this.toggleTimer());
        this.resetButton.addEventListener('click', () => this.resetTimer());
        this.durationSlider.addEventListener('input', (e) => this.updateDuration(e));
        this.durationSlider.value = this.duration;
        this.durationDisplay.textContent = this.duration;

        this.updateDisplay();
    }

    toggleTimer() {
        this.isActive = !this.isActive;

        if (this.isActive) {
            this.startTimer();
        } else {
            this.pauseTimer();
        }
        this.updateDisplay();
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
        const playButtonIcon = this.playButton.querySelector('img');
        playButtonIcon.src = this.isActive ? 
            'images/icons/pause.svg' : 
            'images/icons/play.svg';
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
        "Key": /^topics|^cluster/,
        "Tags": /^tags|^drilldown|^dispatch\/Tags/,
        "Events": /^events|^dispatch\/Events/,
        "About": /^about/
    }

    let openPage = framePage();
    for (let item of gNavBar.querySelector(".main-nav").querySelectorAll("li")) {
        let firstMenuWord = item.querySelector("a").textContent.match(/[a-zA-Z]*/)[0];
        if (pagesWithin[firstMenuWord]?.test(openPage))
            item.classList.add("highlighted")
        else
            item.classList.remove("highlighted");
    }
}

function configurePopupMenus(loadedFrame) {
    // Set triggers for select.sublink-dropdown items on the page

    for (let menu of loadedFrame.querySelectorAll(".sublink-popup select")) {
        menu.addEventListener("change",function (event) {
            openLocalPage(event.target.value);
            debugLog("Selection changed to",event.target.value);
        })
    }
    for (let menu of loadedFrame.querySelectorAll(".sublink2-popup select")) {
        menu.addEventListener("change",function (event) {
            openLocalPage(event.target.value);
            debugLog("Selection changed to",event.target.value);
        })
    }
}

function initializeHomepage() {
    // This code to configure the homepage runs only for homepage.html
    let featuredExcerptContainer = document.getElementById("todays-excerpt");
    if (!featuredExcerptContainer)
        return;
    
    gMeditationTimer.reloadPage();
    document.getElementById("details-link").addEventListener("click",function() {
        gSearchFeaturedOffset = 0; // The details link always goes to the excerpt featured on the homepage
    });
    featuredExcerptContainer.innerHTML = gFeaturedDatabase.excerpts[gFeaturedDatabase.calendar[gTodaysExcerpt]].shortHtml;
    configureLinks(featuredExcerptContainer,"search/homepage.html");
        // links in excerpts are relative to depth 1 pages

    updateDate();
}

function initializeSearchFeatured() {
    // This initialization code runs only for search/Featured.html
    let prevButton = document.getElementById("random-prev");
    let nextButton = document.getElementById("random-next");
    if (prevButton || nextButton) {
        prevButton.onclick = () => { displayNextFeaturedExcerpt(-1); };
        nextButton.onclick = () => { displayNextFeaturedExcerpt(1); };
        displayNextFeaturedExcerpt(0);
    }
}

export async function loadHomepage(loadedFrame) {
    // Called every time a page is loaded.
    // Load gFeaturedDatabase and wire the needed elements

    dropdownMenuClick(null); // Close all dropdown menus
    gNavBar.querySelector('.main-nav').classList.remove("active");
    
    if (!gFeaturedDatabase) {
        await fetch('./assets/FeaturedDatabase.json')
        .then((response) => response.json())
        .then((json) => {
            gFeaturedDatabase = json; 
            debugLog("Loaded homepage database.");
        });
        initializeTodaysExcerpt()
    }

    highlightNavMenuItem();
    configurePopupMenus(loadedFrame);

    initializeHomepage();
    initializeSearchFeatured();
    lucide.createIcons(lucide.icons);
}

function dropdownMenuClick(clickedItem) {
    // Toggle the menu item clicked (a div.dropdown element)
    // Close all other menus; clickedItem === null closes all menus.
    gNavBar.querySelectorAll('.dropdown').forEach(function(dropdownMenu) {
        if (dropdownMenu === clickedItem)
            dropdownMenu.classList.toggle('menu-open');
        else
            dropdownMenu.classList.remove('menu-open');
    });

    // The same for the floating search bar
    let searchBar = gNavBar.querySelector('.floating-search');
    if (clickedItem === document.getElementById('nav-search-icon')) {
        searchBar.classList.toggle('active');
    } else
        searchBar.classList.remove('active');
    if (searchBar.classList.contains('active')) {
        let searchBar = document.getElementById('floating-search-input');
        searchBar.focus();
        searchBar.value = gQuery;
        loadSearchDatabase(); // load the search database in preparation for displaying how many excerpts we've found
        if (searchBar.value.trim()) // If the search bar contains text, display the auto complete menu
            setTimeout(function() {
                gAutoComplete.start();
                countFoundExcerpts();
            },200);
    } else {
        document.getElementById('floating-search-input').blur();
        displayExcerptCount(0);
    }
    
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
        inputBox.blur();
        let searchQuery = encodeURIComponent(inputBox.value);
        inputBox.value = "";
        gQuery = "";
        debugLog('Search bar search for',searchQuery);
        event.preventDefault();
        openLocalPage("search/Text-search.html",`q=${searchQuery}&search=all`);
    });

    /* Uncomment this code to begin working on #113: Grid menu matching abhayagiri.org
    // Clicking Abhayagiri icon toggles the Abhayagiri grid menu
    document.getElementById('nav-abhayagiri-icon').addEventListener('click', function() {
        dropdownMenuClick(this);
    });
    */

    // Keyboard shortcuts
    document.addEventListener("keydown", function(event) {
        // '/' key opens the search bar if it's not open already
        if ((event.key === "/") && !gNavBar.querySelector('.floating-search.active')) {
            event.preventDefault();
            document.getElementById("nav-search-icon").click();
        }
        // Esc key closes all menus if any are open
        if ((event.key === "Escape") && gNavBar.querySelector('.active')) {
            event.preventDefault();
            dropdownMenuClick(null);
            gNavBar.querySelector('.main-nav').classList.remove("active");
        }
    });
}

let gAutoCompleteDatabase = {};
let gQuery = "";
let gAutoComplete = null;

function setupAutoComplete() {
    // Code to configure floating menu autocomplete functionality
    // See https://tarekraafat.github.io/autoComplete.js/#/usage for details
    gAutoComplete = new autoComplete({
        selector: "#floating-search-input",
        placeHolder: "Search the teachings...",
        diacritics: true, // Don't be picky about diacritics
        data: {
            src: async () => {
                try {
                    // Fetch External Data Source
                    const source = await fetch("assets/AutoCompleteDatabase.json");
                    gAutoCompleteDatabase = await source.json();
                    // Returns Fetched data
                    return gAutoCompleteDatabase;
                } catch (error) {
                    return error;
                }
            },
            keys: ["short","long","number"],
            cache: true,
            filter: (results) => {
                // Filter entries that link to the same file
                let links = new Set();
                return results.filter((item) => {
                    if (item.key === "number" && item.value.number !== gQuery)
                        return false; // Number search must match exactly
                    if (links.has(item.value.link))
                        return false; // Remove items that link to identical pages
                    links.add(item.value.link);
                    return true;
                });
            },
        },
        submit: true,
        query: (input) => {
            // Don't search if the input contains blob control characters not used for other purposes
            if (/[\]\[(){}<>&^#]/.test(input)) {
                gQuery = "";
                return "";
            }

            input = input.replace(/^\s+/,""); // Strip leading whitespace
            input = input.replace(/\s+/," ") // Convert all whitespace to single spaces
            input = input.trim() ? input : ""; // Don't search if it's only whitespace
            gQuery = input;
            return input;
        },
        resultItem: {
            highlight: true
        },
        resultsList: {
            maxResults: 15,
            element: (list,data) => {
                if (data.results.length < data.matches.length) {
                    const info = document.createElement("p");
                    info.innerHTML = `Showing <b>${data.results.length}</b> out of <b>${data.matches.length}</b> results`;
                    list.append(info);
                }
                lucide.createIcons(lucide.icons); // Render the icons after building the list
            }
        },
        events: {
            input: {
                selection: (event) => {
                    const selection = event.detail.selection.value;

                    debugLog("Selected",selection.icon,selection.long);
                    let inputBox = document.getElementById('floating-search-input');
                    inputBox.blur();
                    inputBox.value = "";
                    gQuery = "";
                    openLocalPage(selection.link)
                },
            }
        },
        resultItem: {
            element: (item, data) => {
                // Modify Results Item Style
                // item.style = "display: flex;";
                // Modify Results Item Content
                let matchText = data.key === "number" ? data.value.short : data.match;
                let icon = data.value.icon;
                if (icon && !icon.match("<"))
                    icon = `<i data-lucide="${icon}"></i>`
                let suffix = data.value.suffix;
                if (data.value.excerptCount)
                    suffix += ` (${data.value.excerptCount})`;
                item.innerHTML = `${icon} ${matchText} ${suffix}`;
            },
            highlight: true,
        }
    });
}

function readingFaithfullyLink(baseLink) {
    // Given a link to suttacentral.net, return a link to the same text on sutta.readingfaithfully.org.
    // Return null if the link doesn't point to suttacentral.

    const prefix = "https://suttacentral.net/";
    const suttas = ['dn','mn','sn','an','kp','dhp','ud','iti','snp','vv','pv','thag','thig','ja','bupj','buss','buay','bunp','bupc','bupd','busk','buas','bipj','biss','binp','bipc','bipd','bisk','bias','kd','pvr','mil'];
    const doubleRefs = ['sn','an','ud','','snp','thag','thig'];
    if (!baseLink.startsWith(prefix))
        return null;
    let suttaRef = baseLink.replace(prefix,"").toLowerCase().split("/")[0];
    let match = suttaRef.match(/^([^0-9]+)([0-9]+)(.[0-9]+)?/);
    if (match && suttas.includes(match[1])) {
        let numbers = match[2];
        if (match[3] && doubleRefs.includes(match[1]))
            numbers += match[3];
        return `https://sutta.readingfaithfully.org/?q=${match[1]}${numbers}`
    } else
        return null;
}

function setupOptionalSuttaRefs() {
    // Configure event listeners to link suttas to https://sutta.readingfaithfully.org/ when the alt/option key is pressed.

    document.addEventListener("click", function(event) {
        if (event.altKey && event.target.href) {
            let newHref = readingFaithfullyLink(event.target.href);
            debugLog("Alt link:",newHref);
            if (newHref) {
                event.preventDefault();
                window.open(newHref,"_blank");
            }
        }
    });
}

function displayExcerptCount(itemsFound) {
    // Display the number of excerpts found in the floating search bar

    let text = itemsFound ? `${itemsFound} excerpt${itemsFound > 1 ? "s" : ""}` : "";
    document.getElementById("found-count").innerText = text;
}

function countFoundExcerpts() {
    let query = document.getElementById("floating-search-input").value.trim();
    if (!query) {
        displayExcerptCount(0);
        return;
    }
    let searchGroups = new SearchQuery(query);
    gSearchers["x"].search(searchGroups);
    displayExcerptCount(gSearchers["x"].foundItems.length);
}

let gMeditationTimer = null;
document.addEventListener('DOMContentLoaded', () => {
    // Called only once after pages/index.html DOM is loaded
    debugLog("DOMContentLoaded event");
	configureLinks(document.querySelector("header"),"index.html");
	configureLinks(document.querySelector("footer"),"index.html");

    setupNavMenuTriggers();
    gMeditationTimer = new MeditationTimer();

    // Display the number of excerpts found with this search
    document.getElementById("floating-search-input").addEventListener("input",countFoundExcerpts);

    setupAutoComplete();
    setupOptionalSuttaRefs();

    if (DEBUG) { // Configure keyboard shortcuts to change homepage featured excerpt
        document.addEventListener("keydown", function(event) {
            if ((event.key === "ArrowLeft") || (event.key === "ArrowRight")) {
                if (event.key === "ArrowLeft")
                    gDebugDateOffset -= 1
                else
                    gDebugDateOffset += 1
                let debugDate = new Date();
                debugDate.setDate(debugDate.getDate() + gDebugDateOffset);
                initializeTodaysExcerpt(debugDate);
                let featuredExcerptContainer = document.getElementById("todays-excerpt");
                if (featuredExcerptContainer) {
                    featuredExcerptContainer.innerHTML = gFeaturedDatabase.excerpts[gFeaturedDatabase.calendar[gTodaysExcerpt]].shortHtml;
                    configureLinks(featuredExcerptContainer,"search/homepage.html");
                    updateDate(debugDate);
                }
            }
        });
    }
});