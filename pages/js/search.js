import {configureLinks,frameSearch,setFrameSearch,scrollToInitialPosition, loadDatabase} from './frame.js';
import { loadToggleView } from './toggle-view.js';

const TEXT_DELIMITERS = "][{}<>^";
const METADATA_DELIMITERS = "#&@";
const METADATA_SEPERATOR = "|"
const SPECIAL_SEARCH_CHARS = TEXT_DELIMITERS + METADATA_DELIMITERS + "()";

const HAS_METADATADELIMITERS = new RegExp(`.*[${METADATA_DELIMITERS}]`);

const PALI_DIACRITICS = {
    "a":"ā","i":"ī","u":"ū",
    "d":"ḍ","l":"ḷ","t":"ṭ",
    "n":"ñṇṅ","m":"ṁṃ",
    "'": '‘’"“”'                // A single quote matches all types of quotes
};

let PALI_DIACRITIC_MATCH_ALL = {};
Object.keys(PALI_DIACRITICS).forEach((letter) => {
    PALI_DIACRITIC_MATCH_ALL[letter] = `[${letter}${PALI_DIACRITICS[letter]}]`;
});

const DEBUG = false;

export function regExpEscape(literal_string) {
    return literal_string.replace(/[-[\]{}()*+!<>=:?.\/\\^$|#\s,]/g, '\\$&');
}

const ESCAPED_HTML_CHARS = regExpEscape(SPECIAL_SEARCH_CHARS);
const MATCH_END_DELIMITERS = new RegExp(`^\\\\[${regExpEscape(TEXT_DELIMITERS)}]+|\\\\[${regExpEscape(TEXT_DELIMITERS)}]+$`,"g");

function capitalizeFirstLetter(val) {
    return String(val).charAt(0).toUpperCase() + String(val).slice(1);
}

const encodedSearchChars = ["?","=","#","&",":","/","%"];
export function encodeSearchQuery(query) {
    let encodeDict = {};
    for (let n = 0; n < encodedSearchChars.length; n++) {
        encodeDict[encodedSearchChars[n]] = String.fromCharCode(0xA4 + n);
    }
    let encodeRegExp = new RegExp(`[${encodedSearchChars.join("")}]`,"g")
    return query.replaceAll(encodeRegExp,(c) => encodeDict[c])
} 

function decodeSearchQuery(query) {
    let decodeDict = {};
    for (let n = 0; n < encodedSearchChars.length; n++) {
        decodeDict[String.fromCharCode(0xA4 + n)] = encodedSearchChars[n];
    }
    let decodeRegExp = new RegExp(`[${encodeSearchQuery(encodedSearchChars.join(""))}]`,"g")
    return query.replaceAll(decodeRegExp,(c) => decodeDict[c])
}


function nbsp(count) {
    return "&nbsp;".repeat(count);
}

function modulus(numerator,denominator) {
    return ((numerator % denominator) + denominator) % denominator;
}

export async function loadSearchDatabase() {
    if (!gSearchDatabase) {
        await loadDatabase('SearchDatabase.json')
        .then((json) => {
            gSearchDatabase = json; 
            debugLog("Loaded search database.");
            for (let code in gSearchers) {
                gSearchers[code].loadItemsFomDatabase(gSearchDatabase)
            }
        });
    }
}

export async function loadSearchPage() {
    // Called when a search page is loaded. Load the database, configure the search button,
    // fill the search bar with the URL query string and run a search.

    let searchButtonsFound = 0;
    for (let searchCode in gSearchers) {
        let searchButton = document.getElementById(`search-${searchCode}-button`);
        if (searchButton) {
            searchButton.addEventListener("click",function(event) {
                searchButtonClick(searchCode);
                event.preventDefault();
            });
            searchButtonsFound += 1;
        }
    }

    if (!searchButtonsFound)
        return;

    let params = frameSearch();
    let query = params.has("q") ? decodeURIComponent(params.get("q")) : "";
    if (!query)
        document.getElementById("search-text").focus();

    await loadSearchDatabase();

    searchFromURL();
    if (query) // Set the scroll position after displaying search results.
        scrollToInitialPosition();
}

function matchEnclosedText(separators,dontMatchAfterSpace) {
    // Return a regex string that matches the contents between separators.
    // Separators is a 2-character string like '{}'
    // Match all characters excerpt the end character until a space is encountered.
    // After a space if any characters in dontMatchAfterSpace are encountered, don't match the text.
    // If the end character is encountered, match it.

    let escapedStart = regExpEscape(separators[0]);
    let escapedEnd = regExpEscape(separators[1]);
    
    return [escapedStart,
        `[^${escapedEnd} ]*`,
        "(?:",
            `[^${escapedEnd + regExpEscape(dontMatchAfterSpace)}]*`,
            escapedEnd,
        ")"
    ].join("");
}

function matchQuotes(quoteChar) {
    // Returns a regex string that matches the content between quoteChar.
    // Only stops when another quoteChar or the end of this string is encountered.

    let escapedQuoteChar = regExpEscape(quoteChar);
    return `${escapedQuoteChar}[^${escapedQuoteChar}]*${escapedQuoteChar}?`;
}

function substituteWildcards(regExpString) {
    // Convert the following wildcards to RegExp strings:
    // * Match any or no characters
    // _ Match exactly one character
    // $ Match word boundaries

    // Strip off leading and trailing * and $. The innermost symbol determines whether to match a word boundary.
    let bounded = regExpEscape(regExpString.replace(/^[$*]+/,"").replace(/[$*]+$/,""));
    if (regExpString.match(/^[$*]*/)[0].endsWith("$"))
        bounded = "\\b" + bounded;
    if (regExpString.match(/[$*]*$/)[0].startsWith("$"))
    bounded += "\\b";

    // Replace inner * and _ and $ with appropriate operators.
    return bounded.replaceAll("\\*",`[^${ESCAPED_HTML_CHARS}]*?`).replaceAll("_",`[^${ESCAPED_HTML_CHARS}]`).replaceAll("\\$","\\b");
}

class SearchBase {
    // Abstract search class; matches either nothing or everything depending on negate
    negate = false; // This flag negates the search

    matchesItem(item) { // Does this search group match an item?
        return this.negate;
    }

    filterItems(items) { // Return an array containing items that match this group
        let result = [];
        for (const item of items) {
            if (this.matchesItem(item))
                result.push(item)
        }
        return result;
    }

    regExpBits() { 
        // Return a list of regular expressions included in the search.
        // Used to sort the search results.

        return [];
    }
}

// A class to parse and match a single term in a search query
class SearchTerm extends SearchBase {
    matcher; // A RegEx created from searchElement
    matchesMetadata = false; // Does this search term apply to metadata?
    rawRegExp = false; // Was this created from a raw regular expression enclosed in backquotes?
    boldTextMatcher = ""; // A RegEx string used to highlight this term when displaying results

    constructor(searchElement) {
        // Create a searchTerm from an element found by parseQuery.
        // Also create boldTextMatcher to display the match in bold.
        super();

        this.matchesMetadata = HAS_METADATADELIMITERS.test(searchElement);
        this.rawRegExp = searchElement.startsWith("`");

        let finalRegEx = "";
        let escaped = "";
        if (this.rawRegExp) {
            finalRegEx = searchElement.replace(/^`/,"").replace(/`$/,""); // Remove enclosing `
            escaped = finalRegEx;
            debugLog("raw RegExp:",finalRegEx);
        } else {
            if (/^[0-9]+$/.test(searchElement)) // Enclose bare numbers in quotes so 7 does not match 37
                searchElement = '"' + searchElement + '"'

            let qTagMatch = false;
            let aTagMatch = false;
            if (/\]\/\/$/.test(searchElement)) { // Does this query match qTags only?
                searchElement = searchElement.replace(/\/*$/,"");
                qTagMatch = true;
            }
            if (/^\/\/\[/.test(searchElement)) { // Does this query match aTags only?
                searchElement = searchElement.replace(/^\/*/,"");
                aTagMatch = true;
            }
            
            // Replace quote marks at beginning and end with word boundary markers '$' 
            let unwrapped = searchElement.replace(/^"+/,'$').replace(/"+$/,'$');
            // Remove $ boundary markers if the first/last character is not a word character
            unwrapped = unwrapped.replace(/^\$(?=\W)/,"");
            unwrapped = unwrapped.replace(/(\W)\$$/,"$1");
            // Replace inner * and $ with appropriate operators.
            escaped = substituteWildcards(unwrapped);
            

            finalRegEx = escaped;
            if (qTagMatch) {
                finalRegEx += "(?=.*//)";
            }
            if (aTagMatch) {
                finalRegEx += "(?!.*//)";
            }
            debugLog("searchElement:",searchElement,finalRegEx);
        }
        try {
            this.matcher = new RegExp(finalRegEx);
        } catch (err) {
            console.error(err);
            throw new Error(`Invalid ${this.rawRegExp ? "regular expression" : "search term"}: ${searchElement}`);
        }
        

        if (this.matchesMetadata)
            return; // Don't apply boldface to metadata searches or negated character classes

        // Start processing again to create RegExps for bold text
        let boldItem = escaped;
        debugLog("boldItem before:",boldItem);
        boldItem = boldItem.replaceAll(MATCH_END_DELIMITERS,"");

        for (const letter in PALI_DIACRITIC_MATCH_ALL) {
            const realLetter = new RegExp(`\\\\.|\\[.*?\\]|${letter}`,"g");
            boldItem = boldItem.replaceAll(realLetter,(s) => s === letter ? PALI_DIACRITIC_MATCH_ALL[letter] : s);
                // Match all diacritics of actual letters, but don't change RegExp operators
        }

        debugLog("boldItem after:",boldItem);
        this.boldTextMatcher = boldItem;
    }

    matchesBlob(blob) { // Does this search term match a given blob?
        if (!this.matchesMetadata) {
            blob = blob.split(METADATA_SEPERATOR)[0];
        }
        return this.matcher.test(blob);
    }

    matchesItem(item) { // Does this search group match an item?
        for (const blob of item.blobs) {
            if (this.matchesBlob(blob))
                return !this.negate;
        }
        return this.negate;
    }

    regExpBits() {
        return this.negate ? [] : [this.matcher];
    }

    toString() {
        return (this.negate ? "!`" : "`") + this.matcher.source +"`"
    }
}

class SearchGroup extends SearchBase {
    // An array of searchTerms. Subclasses define different operations (and, or, single item match)
    terms = []; // An array of searchBase items
    prefixChar = ""; // The prefix character for this search type

    constructor() {
        super()
    }

    addTerm(searchString) {
        this.terms.push(new SearchTerm(searchString));
    }

    matchesItem(item) { // Does this search group match an item?
        return this.negate; // Subclasses must implement this for functionality
    }

    get boldTextMatcher() {
        // Join the regular expressions of our terms with "|" to match any of them
        let boldRegExps = this.terms.map((term) => term.boldTextMatcher).filter((regExp) => regExp);
        return boldRegExps.join("|");
    }

    regExpBits() {
        if (this.negate)
            return [];
        let bits = [];
        for (let term of this.terms) {
            bits = bits.concat(term.regExpBits());
        }
        return bits;
    }

    toString() {
        console.log(this)
        return `${this.negate ? "!" : ""}${this.prefixChar}(${this.terms.map((term) => String(term)).join(" ")})`;
    }
}

class SearchAnd extends SearchGroup {
    // This class matches an item only if all of its terms match the item.
    prefixChar = "&";

    matchesItem(item) { // Does this search group match an item?
        for (const term of this.terms) {
            if (!term.matchesItem(item))
                return this.negate;
        }
        return !this.negate;
    }
}

class SearchOr extends SearchGroup {
    // This class matches an item if any of its terms match the item.
    prefixChar = "|";

    matchesItem(item) { // Does this search group match an item?
        for (const term of this.terms) {
            if (term.matchesItem(item))
                return !this.negate;
        }
        return this.negate;
    }
}

class SingleItemSearch extends SearchGroup {
    // This class matches an item only if all of its terms match a single blob within that item.
    // This can be used to match excerpts containing stories with tag [Animal]
    // as distinct from excerpts containing a story annotation and the tag [Animal] applied elsewhere.
    prefixChar = "~";

    matchesItem(item) { // Does this search group match an item?
        for (const blob of item.blobs) {
            let allTermsMatch = true;
            let singleBlobItem = {"blobs":[blob]};
            for (const term of this.terms) {
                if (!term.matchesItem(singleBlobItem))
                    allTermsMatch = false;
            }
            if (allTermsMatch)
                return !this.negate;
        }
        return this.negate;
    }
}

export class SearchQuery {
    // An array of searchGroups that describes an entire search query
    searcher; // A searchGroup representing the query
    queryText; // The text of the query
    boldTextRegex; // A regular expression matching found texts which should be displayed in bold

    constructor(queryText,strict=false) {
        // Construct a search query by parsing queryText into search groups containing search terms.
        // Search groups are specified by enclosure within parenthesis.
        // The types of search group are "&": AND, "|": OR, and "~": SINGLE ITEM AND
        // SINGLE ITEM AND requires all search terms within the group to match in a single blob
        // So ~(#Quote Pasanno}) matches only kind 'Quote' with teacher ending with Pasanno.
        // It does not match excerpts which include Ajahn Pasanno as a teacher and have quotes by someone else.
        
        // 0. Convert query to lowercase and remove diacritics
        queryText = queryText.replaceAll(/\\.|[^\\]+/g,(s) => s.startsWith("\\") ? s : s.toLowerCase());
            // Regular expressions may include character classes with capital letters such as \W
            // Blobs do not contain the character "\", so a non-RegExp query containing "\" won't match anything anyway. 
        queryText = queryText.normalize("NFD").replace(/[\u0300-\u036f]/g, ""); // https://stackoverflow.com/questions/990904/remove-accents-diacritics-in-a-string-in-javascript
        this.queryText = queryText;

        // 1. Build a regex to parse queryText into items
        let regularTextParts = [
            "[^()&|~! ]",        // Any character that can't be the start or end of a group
            "[!](?![&|~]?[(])",  // Any "!" that doesn't begin a group
            "[&|~](?![(])"       // Any "&", "|", or "~" that doesn't begin a group
        ]
        let parts = [
            "[&|~]?\\(",
                // Match the beginning of a search group:
                // & (or blank): AND - Match if all RegExps in this group match a blob in the item
                // |: OR - Match if any RegExp in this group matches a blob in the item
                // ~: Single blob AND: Match if all RegExps match the same blob in the item
            matchQuotes('"'),
                // Match text enclosed in quotes
            matchQuotes('`'),
                // Regular expressions enclosed in backquotes
            matchEnclosedText('{}',SPECIAL_SEARCH_CHARS),
                // Match teachers enclosed in braces
            "/*" + matchEnclosedText('[]',SPECIAL_SEARCH_CHARS) + "\\+?/*",
                // Match tags enclosed in brackets
                // Match the forms: [tag]// (qTag only), //[tag] (aTag only), [tag]+ (fTag only)
            `(?:${regularTextParts.join("|")})+`
                // Match everything else until we encounter a space or the beginning or end of a group
        ];
        let partsSearch = `\\s*\\)|\\s*(!?)(${parts.join("|")})`
        // The final RegExp matches ")" or the optional negation operator "!" followed by any of parts
        debugLog(partsSearch);
        partsSearch = new RegExp(partsSearch,"g");
    
        // 2. Create items and groups from the found parts
        let currentGroup = strict ? new SingleItemSearch() : new SearchAnd();
        let groupStack = [currentGroup];
        for (let match of queryText.matchAll(partsSearch)) {
            if (match[0].trim() === ")") { // ")" ends a group
                if (groupStack.length >= 2) {
                    groupStack.pop();
                    currentGroup = groupStack[groupStack.length - 1];
                }
            } else if (match[2].endsWith("(")) { // "(" begins a new group
                switch(match[2][0]) {
                    case "&":
                    case "(":
                        currentGroup = new SearchAnd();
                        break;
                    case "|":
                        currentGroup = new SearchOr();
                        break;
                    case "~":
                        currentGroup = new SingleItemSearch();
                        break;
                    default:
                        console.assert(0,"Unknown search type",match[2][0]);
                }
                if (match[1])
                    currentGroup.negate = true;

                // Add the new group as an item in the previous group and make it current
                groupStack[groupStack.length - 1].terms.push(currentGroup);
                groupStack.push(currentGroup);
            } else {
                currentGroup.addTerm(match[2].trim());
                if (match[1]) { // Negate expressions preceeded by '!'
                    currentGroup.terms[currentGroup.terms.length - 1].negate = true;
                }
            }
        }
        this.searcher = groupStack[0];

        // 3. Construct the regex to match bold text.
        let textMatchItems = this.searcher.boldTextMatcher;        
        debugLog("textMatchItems",textMatchItems);
        if (textMatchItems)
            this.boldTextRegex = new RegExp(textMatchItems,"gi");
        else
            this.boldTextRegex = /^a\ba/g; // a RegExp that doesn't match anything
        debugLog(this.boldTextRegex);
    }

    setStrict(strict) {
        // Set the strict mode after this object has been constructed.
        let newSearcher = strict ? new SingleItemSearch() : new SearchAnd();
        newSearcher.terms = this.searcher.terms;
        this.searcher = newSearcher;
    }

    filterItems(items) { // Return an array containing items that match all groups in this query
        return this.searcher.filterItems(items);
    }

    displayMatchesInBold(string) { // Add <b> and </b> tags to string to display matches in bold
        let boldRegExp = this.boldTextRegex;
        function boldText(text) {
            // Apply <b> tag to text matches but not html tags
            return /^[<&]/.test(text) ? text : text.replaceAll(boldRegExp,"<b>$&</b>");
        }
        return string.replaceAll(/<b>[^>]*<\/b>|<[^>]*>|&[^;]*;|[^<>&]*/g,boldText).replaceAll("</b><b>","");
            // Remove redundant </b> tags
    }
}

export function renderExcerpts(excerpts,searcher,sessionHeaders) {
    // Convert a list of excerpts to html code by concatenating their html attributes
    // Display strings in boldTextItems in bold.

    let bits = [];
    let lastSession = null;

    for (const x of excerpts) {
        if (x.session !== lastSession) {
            bits.push(sessionHeaders[x.session]);
            lastSession = x.session;
        }
        bits.push(searcher.displayMatchesInBold(x.html));
        bits.push("<hr>");
    }
    return bits.join("\n");
}

function clearSearchResults(message) {
    // Called when the search query is blank
    let messageFrame = document.getElementById('message');
    let instructionsFrame = document.getElementById('instructions');
    let resultsFrame = document.getElementById('results');

    instructionsFrame.style.display = "block";
    resultsFrame.innerHTML = "";

    if (message) {
        messageFrame.innerHTML = message;
        messageFrame.style.display = "block";
    } else
        messageFrame.style.display = "none";
}

function displaySearchResults(message,searchResults) {
    // Display the seach results in the various html frames

    let messageFrame = document.getElementById('message');
    let instructionsFrame = document.getElementById('instructions');
    let resultsFrame = document.getElementById('results');

    instructionsFrame.style.display = "none";

    resultsFrame.innerHTML = searchResults;
    lucide.createIcons(lucide.icons);
    // If we find a subtopic that is itself a tag, change "Tags" to "Other tags"
    let subtopicResults = document.getElementById("results-b");
    if (subtopicResults && document.getElementById("results-g")) {
        if (subtopicResults.querySelector(".lucide-tag")) {
            let tagHeader = resultsFrame.querySelector("#results-g h3");
            tagHeader.innerHTML = tagHeader.innerHTML.replace("Tags","Other tags")
        }
    }

    configureLinks(resultsFrame,location.hash.slice(1));
    loadToggleView(resultsFrame);

    if (message) {
        messageFrame.innerHTML = message;
        messageFrame.style.display = "block";
    } else
        messageFrame.style.display = "none";
}

class Searcher {
    code; // a one-letter code to identify the search.
    name; // the name of the search, e.g. "Tag"
    plural; // the plural name of the search.
    nameInResults = ""; // A longer plural name to display in the search results
                        // e.g. "Sutta and Vinaya texts"
    header = ""; // html header just before the first search result 
    prefix = "<p>"; // html prefix of each search result.
    suffix = "</p>"; // hmtl suffix of each search result.
    separator = ""; // the html code to separate each displayed search result.
    itemsPerPage = null; // The number of items to display per page.
        // itemsPerPage = null displays all items regardless of length.
        // The base class Searcher displays only one page.
    divClass = "listing"; // Enlcose the search results in a <div> tag with this class.
    multiSearchHeading = false; // Should we display a heading for use with MultiSearcher?
    items = []; // A list of items of the form:
        // database[n].blobs: an array of search blobs to match
        // database[n].html: the html code to display this item when found
    query = null; // A searchQuery object describing the search
    foundItems = []; // The items we have found.
    multiSearcher = null; // Set to the MultiSearcher object we are part of.
    
    constructor(code,name) {
        // Configure a search with a given code and name
        this.code = code;
        this.name = name;
        this.plural = this.name + "s";
    }

    loadItemsFomDatabase(database) {
        // Called after SearchDatabase.json is loaded to prepare for searching
        this.items = database.searches[this.code].items;
    }

    search(searchQuery) {
        debugLog(this.name,"search.");
        this.query = searchQuery
        this.foundItems = searchQuery.filterItems(this.items);
    }

    renderItems(startItem = 0,endItem = null) {
        // Convert a list of items to html code by concatenating their html attributes
        // Display strings in boldTextItems in bold.

        if (endItem === null)
            endItem = undefined;
        let rendered = [];
        for (let item of this.foundItems.slice(startItem,endItem)) {
            rendered.push(this.prefix + this.query.displayMatchesInBold(item.html) + this.suffix);
        }

        return rendered.join(this.separator);
    }

    htmlSearchResults() {
        // Return an html string containing the search results.
        // Returns an empty string if the search didn't find anything.
        if (this.foundItems.length > 0) {
            let items = this.renderItems(0,this.itemsPerPage);
            let heading = this.header;
            if (this.multiSearchHeading) { // Match the formatting of TruncatedSearcher
                heading = `\n<h3>${this.foundItemsHeader()}</h3>`;
                items = `<div id="results-${this.code}.b">\n` + this.header + items + `\n</div>`
            }
            return `<div class="${this.divClass}" id="results-${this.code}">${heading}\n${items}\n</div>`;
        } else
            return "";
    }

    foundItemsString() {
        // Returns a string describing the found items in the form "27 tags"
        // Returns "" if no items were found.
        if (this.foundItems.length > 0)
            return `${this.foundItems.length} ${this.foundItems.length > 1 ? this.plural : this.name}`;
        else
            return "";
    }

    foundItemsHeader() {
        // Returns a string describing the found items in the form "Tags (27):"
        // Returns "" if no items were found.

        if (this.foundItems.length > 0)
            return `${capitalizeFirstLetter(this.nameInResults || this.plural)} (${this.foundItems.length}):`;
        else
            return "";
    }

    showResults(message = "") {
        // Display the results of this search in the main window.
        // message is an optional message to display.
        
        if (this.foundItems.length > 0) {
            message += `Found ${this.foundItemsString()}`;
            if (this.itemsPerPage && this.foundItems.length > this.itemsPerPage)
                message += `. Showing only the first ${this.itemsPerPage}:`;
            else
                message += ":"

            displaySearchResults(message,this.htmlSearchResults());
            this.configureResultsFrame(document.getElementById('results'));
        } else {
            message += `No ${this.plural} found.`
            clearSearchResults(message);
        }
    }

    configureResultsFrame(frame) {
        // Called to configure javascript links, etc. within the search results frame.
        // There's nothing to do in the Searcher base class.
    }
}

class TruncatedSearcher extends Searcher {
    // A Searcher that shows only a few results to begin with followed by "Show all...".
    // The whole search can be hidden using a toggle-view object.
    // Displays its own header e.g. "Teachers (2):", so it's intended to be used with MultiSearcher.

    truncateAt; // Truncate the initial view if there are more than this many items
        // If truncateAt === 0, always hide the entire list;
        // if truncateAt < 0, hide all items if there are more than abs(truncateAt)

    constructor(code,name,truncateAt) {
        super(code,name);
        this.truncateAt = truncateAt;
    }

    htmlSearchResults() {
        if (this.foundItems.length === 0)
            return "";

        let resultsId = `results-${this.code}`;

        let firstItems = this.header;
        let moreItems = "";
        if (this.truncateAt > 0 && this.foundItems.length > this.truncateAt) {
            firstItems += this.renderItems(0,this.truncateAt - 1);
            let moreItemsBody = this.renderItems(this.truncateAt - 1);
            moreItems = ` 
            <a class="toggle-view hide-self" id="${resultsId}-more" href="#"><i>Show all ${this.foundItems.length}...</i></a>
            <div id="${resultsId}-more.b" style="display:none;">
            ${moreItemsBody}
            </div>
            `;
        } else {
            firstItems += this.renderItems();
        }
        
        let hideAll = this.truncateAt <= 0 && this.foundItems.length > -this.truncateAt;
        let squareSymbol = hideAll ? "plus" : "minus";
        let hideCode = hideAll ? ` style="display:none"` : "";

        return ` 
        <div class="${this.divClass}" id="results-${this.code}">
        <h3><a><i class="fa fa-${squareSymbol}-square toggle-view" id="${resultsId}"></i></a> ${this.foundItemsHeader()}</h3>
        <div id="${resultsId}.b"${hideCode}>
        ${firstItems} 
        ${moreItems}
        </div>
        </div>
        `;
    }
}

class SessionSearcher extends TruncatedSearcher {
    // Searcher for sessions. Groups sessions by event and displays the event after each group.
    code = "s"; // a one-letter code to identify the search.
    name = "session"; // the name of the search, e.g. "Tag"
    plural = "sessions"; // the plural name of the search.
    truncateAt = -4;
    eventHtml; // The html code to display after each event group

    loadItemsFomDatabase(database) {
        // Called after SearchDatabase.json is loaded to prepare for searching
        super.loadItemsFomDatabase(database);
        this.eventHtml = database.searches[this.code].eventHtml;
    }

    renderItems(startItem = 0,endItem = null) {
        if (endItem === null)
            endItem = undefined;
        let prevEvent = this.foundItems[startItem].event;
        let rendered = [];
        for (let item of this.foundItems.slice(startItem,endItem)) {
            if (item.event !== prevEvent) {
                rendered.push(this.eventHtml[prevEvent]);
                prevEvent = item.event;
            }
            rendered.push(this.prefix + this.query.displayMatchesInBold(item.html) + this.suffix);
        }
        rendered.push(this.eventHtml[prevEvent]);

        return rendered.join(this.separator);
    }
}

class PagedSearcher extends Searcher {
    // Extends Searcher to show multiple pages instead of just one.

    constructor(code,name,itemsPerPage) {
        super(code,name);
        this.itemsPerPage = itemsPerPage;
    }

    htmlSearchResults() {
        // Provide a multi-page view of these excerpts.
        if (!this.foundItems.length)
            return "";

        let pageCount = Math.ceil(this.foundItems.length / this.itemsPerPage);
        if (pageCount === 1) {
            return super.htmlSearchResults();
        }

        let heading = this.multiSearchHeading ? `\n<h3>${this.foundItemsHeader()}</h3>` : "";
        heading += this.header;

        const pageNumberParam = `${this.code}Page`;
        let params = frameSearch(location.hash);
        let currentPage = 1;
        if (params.has(pageNumberParam))
            currentPage = Number(params.get(pageNumberParam));

        let pageMenu = "";
        if (pageCount > 0) {
            let pageNumbers = [...Array(pageCount).keys()].map((n) => (n+1));
            let pageLinks = pageNumbers.map((n) => {
                let newParams = frameSearch(location.hash);
                newParams.set(pageNumberParam,String(n));
                return `<a href="${setFrameSearch(newParams,location)}"${n === currentPage ? 'class="active"' : ''}>${n}</a>`;
            });

            pageMenu = `\n<p class="page-list">Page:&emsp;${pageLinks.join("&emsp;")}</p>`;
        }

        let rendered = this.renderItems((currentPage - 1) * this.itemsPerPage,currentPage * this.itemsPerPage);
        return `<div class="${this.divClass}" id="results-${this.code}">${heading}${pageMenu}\n${rendered}\n${pageMenu}</div>`;
    }

    showResults(message = "") {
        // Display the results of this search in the main window.
        // message is an optional message to display.
        
        if (DEBUG)
            message += `Processed query: ${String(this.query.searcher)}<br>`

        if (this.foundItems.length > 0) {
            message += `Found ${this.foundItemsString()}:`;
            displaySearchResults(message,this.htmlSearchResults());
            this.configureResultsFrame(document.getElementById('results'));
        } else {
            message += `No ${this.plural} found.`
            clearSearchResults(message);
        }
    }

    configureResultsFrame(resultsFrame) {
        // Set click listeners to the page menus so we don't have to redo the search.
        let secondMenu = false;
        for (let menu of resultsFrame.getElementsByClassName("page-list")) {
            for (let item of menu.getElementsByTagName("a")) {
                item.scrollToTop = secondMenu;
                item.addEventListener("click", (event) => {
                    let pageNumber = event.target.innerHTML;
                    let params = frameSearch(location.hash);
                    params.set(`${this.code}Page`,pageNumber);
                    setFrameSearch(params);
                    if (this.multiSearcher)
                        this.multiSearcher.showResults();
                    else
                        this.showResults();
                    if (event.target.scrollToTop) {
                        let resultsFrame = document.getElementById(`results-${this.code}`);
                        resultsFrame.scrollIntoView();
                    }
                    event.preventDefault();
                });
            }
            secondMenu = true;
        }
    }
}

function uniqueMatches(regExp,stringList) {
    // Given a regular expression (with /g flag) and a list of strings, return the Set of unique matches
    // Each match must include at least one letter.
    let bits = [];
    for (let s of stringList) {
        regExp.lastIndex = 0;
        for (let match of s.matchAll(regExp)) {
            if (/[a-z]/.test(match))
                bits.push(match);
        }
    }
    return new Set(bits.map(b => b[0]));
}

function countedMatches(matchSet) {
    // Given a set of matches, return an object with two properties:
    // blob: The unordered concatenation of all unique matches (matches must contain at least one letter)
    // count: How many unique matches there are
    
    let bits = [...matchSet];
    return {"blob":bits.join(""), "count": bits.length};
}

function countedText(matchObject) {
    // Given a RegExp match object, return an object with two properties:
    // blob: The matched text itself
    // count: The length of the string divided by 50 characters; minimum 1.0

    if (matchObject)
        return {"blob":matchObject[0], "count": Math.max(matchObject[0].length / 60.0,1.0)}
    else
        return {"blob":"", "count": 0};
}

let gCommonWordBlob = ""; // This is loaded by ExcerptSearcher
class RelevanceWeighter {
    // A class to match blobs against terms of the search query, which returns a weighted sum
    // of the number of terms that match the blob.
    query;                  // The SearchQuery object
    searchParts;            // A list of regular expressions to use for weighting
    fullWordParts;          // Same as searchParts, but matches only word boundaries
    matchesCommonWords;     // A list of booleans indicating whether each element of searchParts matches common words
    entireSearchQuery;      // A dict of RegExp objects that matches the entire search query
                            // entireSearchQuery[firstChar] is used to match blobs that begin with firstChar
    explanation = "";       // A string explaining the last call to weightedMatch

    constructor(query) {
        // query: the SearchQuery object representing the search
        this.query = query;
        this.searchParts = query.searcher.regExpBits();
        this.fullWordParts = this.searchParts.map((regExp) => new RegExp("\\b" + regExp.source + "\\b"));
        this.matchesCommonWords = this.searchParts.map((regExp) => regExp.test(gCommonWordBlob));
        
        // If the query doesn't use special characters, then make regular expressions
        // that match entire text, tag, and teacher blobs
        this.entireSearchQuery = {};
        let specialCharacters = new RegExp(`["\`!${ESCAPED_HTML_CHARS}]`);
        if (!specialCharacters.test(query.queryText)) {
            let fullQuerySearch = new SearchQuery(`"${query.queryText}"`);
            let baseQuery = fullQuerySearch.searcher.regExpBits()[0];

            if (query.queryText.includes(" ")) // Only add additional weight to full text strings if the query contains multiple words
                this.entireSearchQuery["^"] = baseQuery;
            this.entireSearchQuery["["] = new RegExp(`\\[${baseQuery.source}\\]`);
            this.entireSearchQuery["{"] = new RegExp(`\\{${baseQuery.source}\\}`);
        }
    }

    weightedMatch(blob,commonWordWeight = 0.5) {
        // Returns a weighted count of the number of query terms that match this blob
        const fullWordMultiplier = 3;
        const fullQueryMultiplier = 3;

        let fullQuery = 0;
        let fullWords = 0;
        let partialWords = 0;
        let fullQueryMatch = this.entireSearchQuery[blob.slice(0,1)];
        if (fullQueryMatch && fullQueryMatch.test(blob)) {
            fullQuery = 1;
        }
        this.searchParts.forEach((term,index) => {
            if (term.test(blob)) {
                let weight = this.matchesCommonWords[index] ? commonWordWeight : 1;
                if (this.fullWordParts[index].test(blob))
                    fullWords += weight
                else
                    partialWords += weight;
            }
        });
        if (DEBUG) {
            let explanationBits = [];
            if (fullQuery)
                explanationBits.push(`${fullQueryMultiplier}Q`);
            if (fullWords)
                explanationBits.push(`${fullWords}*${fullWordMultiplier}W`);
            if (partialWords)
                explanationBits.push(String(partialWords));
            this.explanation = explanationBits.join("+");
        }
        
        return fullQueryMultiplier*fullQuery + fullQueryMultiplier*fullWords + partialWords;
    }
}

const UNUSED_OPTIONS = `
    <input type="checkbox" class="query-checkbox" id="strict">
    <label for="strict"> Strict search</label>&emsp;
`;
const EXCERPT_SEARCH_OPTIONS = `
<p class="checkboxes">
    <input type="checkbox" class="query-checkbox" id="featured">
    <label for="featured"> Featured excerpts first</label>&emsp;
    <input type="checkbox" class="query-checkbox" id="relevant">
    <label for="relevant"> Sort by relevance</label>
</p>`;

const FEATURED_BLOCK = `<div class="title" id="featured">Featured excerpts (NN) — Play all <button id="playFeatured"></button></div>`;
const OTHER_EXCERPT_BLOCK = `<div class="title" id="featured">Other excerpts</div>`
export class ExcerptSearcher extends PagedSearcher {
    // Specialised search object for excerpts
    code = "x"; // a one-letter code to identify the search.
    name = "excerpt"; // the name of the search, e.g. "Tag"
    plural = "excerpts"; // the plural name of the search.
    header = EXCERPT_SEARCH_OPTIONS;
    prefix = ""; // html prefix of each search result.
    suffix = ""; // hmtl suffix of each search result.
    separator = "<hr>"; // the html code to separate each displayed search result.
    itemsPerPage = 100; // The number of items to display per page.
        // itemsPerPage = 0 displays all items regardless of length.
        // The base class Searcher displays only one page.
    divClass = ""; // Enlcose the search results in a <div> tag with this class.
    sessionHeader = {};   // Contains rendered headers for each session.

    loadItemsFomDatabase(database) {
        // Called after SearchDatabase.json is loaded to prepare for searching
        super.loadItemsFomDatabase(database);
        this.sessionHeader = database.searches[this.code].sessionHeader;
        gCommonWordBlob = database.searches[this.code].commonWordBlob;
        
        // Generate blobs for search weighting
        for (let excerpt of this.items) {
            let qTags = uniqueMatches(/\[[^\]]*?\]/g,[excerpt.blobs[0].split("//")[0]]);
            let aTags = uniqueMatches(/\[[^\]]*?\]/g,excerpt.blobs);
            qTags.forEach((tag) => aTags.delete(tag));
            excerpt.sortBlob = {
                "fTag": countedMatches(uniqueMatches(/\[[^\]]*?\]\+/g,excerpt.blobs)),
                "qTag": countedMatches(qTags),
                "aTag": countedMatches(aTags),
                "teacher": countedMatches(uniqueMatches(/\{[^\}]*?\}/g,excerpt.blobs)),
            }
            let totalTextBlobWeight = 0.0;
            excerpt.blobs.forEach((blob,index) => {
                let key = "text" + String(index);
                excerpt.sortBlob[key] = countedText(blob.match(/\^[^\^]*?\^/));
                totalTextBlobWeight += excerpt.sortBlob[key].count;
            });
            for (let b in excerpt.sortBlob) {
                if (!excerpt.sortBlob[b].count)
                    delete excerpt.sortBlob[b]
                else if (/text(?!0)/.test(b)) // The weight of all annotations is the sum of all text blobs
                    excerpt.sortBlob[b].count = totalTextBlobWeight;
            }

            // Minor adjustments: aTag divisor should include all tags
            if (excerpt.sortBlob.aTag && excerpt.sortBlob.qTag)
                excerpt.sortBlob.aTag.count += excerpt.sortBlob.qTag.count;
            // Don't count teachers with multiple names twice
            if (excerpt.sortBlob.teacher)
                excerpt.sortBlob.teacher.count = excerpt.uniqueTeachers;
        }
    }

    search(searchQuery) {
        // Sort the results after searching
        super.search(searchQuery);
        let params = frameSearch();
        if (!(params.has("featured") || params.has("relevant")))
            return;

        let matcher = new RelevanceWeighter(searchQuery)
        for (let item of this.foundItems) {
            item.searchWeight = 0;
            item.searchExplanation = "";
        }

        if (params.has("featured")) {
            let fTagWeights = {
                "searchedFTag": 900,
                "otherFTag": 100
            };
            for (let item of this.foundItems) {
                if (!item.sortBlob.fTag)
                    continue;
                let explanationBits = [];
                let commonWordWeight = params.has("relevant") ? 0 : 0.5;
                item.searchWeight += fTagWeights["searchedFTag"] * matcher.weightedMatch(item.sortBlob.fTag.blob,commonWordWeight);
                if (matcher.explanation && DEBUG)
                    explanationBits.push(`(${matcher.explanation})*${fTagWeights.searchedFTag}`);
                // If we are sorting by featured only or a search term matches one of the fTags,
                // prioritize excerpts which have more fTags.
                if ((!params.has("relevant") || item.searchWeight)) {
                    item.searchWeight += item.sortBlob.fTag.count * fTagWeights["otherFTag"];
                    if (matcher.explanation && DEBUG)
                        explanationBits.push(`${item.sortBlob.fTag.count}O*${fTagWeights["otherFTag"]}`)
                }
                if (explanationBits.length > 0)
                    item.searchExplanation = `fTag:[${explanationBits.join(" + ")}]`;
            }
        }
        if (params.has("relevant")) {
            let searchWeights = {
                "qTag": 7.0,
                "aTag": 2.0,
                "teacher": 2.0,
                "text0": 3.0,
                "aText": 1.0
            };

            for (let item of this.foundItems) {
                let explanationBits = item.searchExplanation ? [item.searchExplanation] : [];
                for (let blobKind in item.sortBlob) {
                    if (blobKind == "fTag")
                        continue; // fTags are weighted above
                    let matchCount = matcher.weightedMatch(item.sortBlob[blobKind].blob);
                    if (matchCount) {
                        let weight = (searchWeights[blobKind] || searchWeights.aText);
                        item.searchWeight += matchCount * weight * (1 + 0.5 / item.sortBlob[blobKind].count);
                        if (DEBUG)
                            explanationBits.push(`${blobKind}:[(${matcher.explanation})(${weight}*/${item.sortBlob[blobKind].count.toFixed(1)})]`);
                    }
                }
                if (DEBUG)
                    item.searchExplanation = explanationBits.join(" + ");
            }
        }

        // b - a sorts in descending order
        this.foundItems.sort((a,b) => b.searchWeight - a.searchWeight);
    }

    renderItems(startItem = 0,endItem = null) {
        // Convert a list of excerpts to html code by concatenating their html attributes and
        // inserting session headers where needed.
        // Display strings in boldTextItems in bold.

        if (endItem === null)
            endItem = undefined;

        let bits = [];
        let lastSession = null;

        let params = frameSearch();
        let headerlessFormat = params.has("featured") || params.has("relevant");

        if (headerlessFormat)
            bits.push("<hr>")
        else if (this.multiSearchHeading && (this.foundItems.length <= this.itemsPerPage))
            bits.push("<br/>");

        let displayItems = this.foundItems.slice(startItem,endItem);
        let insideFeaturedBlock = false;
        if (params.has("featured") && this.foundItems[startItem].sortBlob.fTag) {
            let featuredCount = 0;
            while ((featuredCount < displayItems.length) && displayItems[featuredCount].sortBlob.fTag) {
                featuredCount += 1;
            }
            bits.push('<div class="featured">');
            let featuredBlock = FEATURED_BLOCK.replace("NN",String(featuredCount));
            if (featuredCount === 1)
                featuredBlock = featuredBlock.replace("excerpts","excerpt");
            bits.push(featuredBlock);
            insideFeaturedBlock = true;
        }
        for (const x of displayItems) {
            if ((x.session !== lastSession) && !headerlessFormat) {
                bits.push(this.sessionHeader[x.session]);
                lastSession = x.session;
            }
            if (insideFeaturedBlock && !x.sortBlob.fTag) {
                bits.pop();
                bits.push("</div>");
                bits.push(this.separator);
                bits.push(OTHER_EXCERPT_BLOCK);
                insideFeaturedBlock = false;
            }
            let excerptHtml = x.html;
            if (headerlessFormat) {
                excerptHtml = excerptHtml.replace(/<span class="excerpt-number">.*?<\/span>/s,"")
            } else {
                excerptHtml = excerptHtml.replace(/<p class="x-cite">.*?<\/p>/s,"")
            }
            if (DEBUG && headerlessFormat)
                bits.push(`${x.searchExplanation} = ${x.searchWeight.toFixed(2)}`);
            bits.push(this.query.displayMatchesInBold(excerptHtml));
            bits.push(this.separator);
        }
        if (insideFeaturedBlock)
            bits.push("</div>");
        return bits.join("\n");
    }
}

class MultiSearcher {
    // Conduct multiple searches with the same search query
    // Uses duck typing to behave like a Searcher without inheriting from it.

    code; // a one-letter code to identify the search.
    separator = "<hr>"; // the html code to separate each displayed search.
    query = null; // a searchQuery object describing the search
    searches = []; // a list of Searcher objects describing what to search for

    constructor(code, ...searches) {
        this.code = code;
        this.searches = searches;
        for (let s of this.searches) {
            s.multiSearchHeading = true;
            s.multiSearcher = this;
        }
    }

    loadItemsFomDatabase(database) {
        for (let s of this.searches) {
            s.loadItemsFomDatabase(database);
        }
    }

    search(searchQuery) {
        debugLog("Multisearch.");
        this.query = searchQuery;
        for (let s of this.searches) {
            s.search(searchQuery);
        }
    }

    successfulSearches() {
        // Returns the number of searches that found anything.
        let successful = 0;
        for (let s of this.searches) {
            if (s.foundItems.length > 0)
                successful += 1;
        }
        return successful;
    }

    showResults(message = "") {
        // Show the results of all our searches combined.
        // message is an optional message to display.
        
        if (this.successfulSearches()) {
            let searchMessages = this.searches.map((s) => s.foundItemsString());
            searchMessages = searchMessages.filter((s) => s.length > 0);
            if (searchMessages.length > 2)
                message += `Found ${searchMessages.slice(0,-1).join(", ")}, and ${searchMessages[searchMessages.length - 1]}.`;
            else if (searchMessages.length > 1)
                message += `Found ${searchMessages[0]} and ${searchMessages[1]}.`;
            else
                message += `Found ${searchMessages[0]}.`;

            let searchResults = this.searches.map((s) => s.htmlSearchResults());
            searchResults = searchResults.filter((s) => s.length > 0);
            displaySearchResults(message,'<hr style="margin-top: 0px;">' + searchResults.join(this.separator));

            for (let s of this.searches) {
                let resultFrame = document.getElementById(`results-${s.code}`);
                if (resultFrame)
                    s.configureResultsFrame(resultFrame);
            }
        } else {
            message += `No items found.`
            clearSearchResults(message);
        }
    }
}

function searchFromURL() {
    // Find excerpts matching the search query from the page URL.
    if (!gSearchDatabase) {
        debugLog("Error: database not loaded.");
        return;
    }

    let params = frameSearch();
    let query = params.has("q") ? decodeSearchQuery(decodeURIComponent(params.get("q"))) : "";
    let searchKind = params.has("search") ? decodeURIComponent(params.get("search")) : "all";

    debugLog("Called searchFromURL. Query:",query);
    frame.querySelector('#search-text').value = query;

    if (!query.trim()) {
        clearSearchResults();
        return;
    }

    try {
        let searchGroups = new SearchQuery(query,params.has("strict"));
        debugLog(searchGroups);
    
        gSearchers[searchKind].search(searchGroups);
        gSearchers[searchKind].showResults();
    } catch (err) {
        if (err.message.startsWith("Invalid regular expression")) {
            clearSearchResults(err.message);
        } else
            throw err;
    }
}

export function readSearchBar() {
    // Returns the query string corresponding to what's in the search bar right now.

    let searchInput = frame.querySelector('#search-text');
    let query = searchInput.value;
    return encodeURIComponent(encodeSearchQuery(query));
}

function searchButtonClick(searchKind) {
    // Read the search bar text, push the updated URL to history, and run a search.
    let searchInput = frame.querySelector('#search-text');
    searchInput.blur();
    let query = readSearchBar();
    debugLog("Called runFromURLSearch. Query:",query,"Kind:",searchKind);

    let params = frameSearch();
    let newSearch = {q : query,search : searchKind};
    if (params.has("featured"))
        newSearch.featured = "";
    if (params.has("relevant"))
        newSearch.relevant = "";
    let search = new URLSearchParams(newSearch);
    history.pushState({},"",location.href); // First push a new history frame
    setFrameSearch(search); // Then replace the history with the search query

    searchFromURL();
}

let gSearchDatabase = null; // The global search database, loaded from assets/SearchDatabase.json

let gTextSearcher = new TruncatedSearcher("p","text",8);
gTextSearcher.nameInResults = "Sutta and Vinaya texts";
let gAllTextSearcher = new TruncatedSearcher("p","text",-2);
gAllTextSearcher.nameInResults = "Sutta and Vinaya texts";
export let gSearchers = { // A dictionary of searchers by item code
    "x": new ExcerptSearcher(),
    "multi-tag": new MultiSearcher("multi-tag",
        new Searcher("k","key topic"),
        new Searcher("b","subtopic"),
        new Searcher("g","tag")
    ),
    "t": new Searcher("t","teacher"),
    "e": new Searcher("e","event"),
    "all": new MultiSearcher("all",
        new TruncatedSearcher("k","key topic",3),
        new TruncatedSearcher("b","subtopic",5),
        new TruncatedSearcher("g","tag",5),
        new TruncatedSearcher("t","teacher",5),
        new TruncatedSearcher("e","event",3),
        new SessionSearcher(),
        gAllTextSearcher,
        new TruncatedSearcher("o","book",-2),
        new ExcerptSearcher(),
    ),
    "ref": new MultiSearcher("ref",
        gTextSearcher,
        new TruncatedSearcher("o","book",8),
        new TruncatedSearcher("a","author",4),
    ),
};
