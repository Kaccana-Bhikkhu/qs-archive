import posix from "./path.js";
import { loadSearchPage } from "./search.js";
import { loadHomepage } from "./homepage.js";
import { loadToggleView } from "./toggle-view.js";
const { join, dirname } = posix;
const frame = document.querySelector("div#frame");
const titleEl = document.querySelector("title");
const absoluteURLRegex = "^(//|[a-z+]+:)";
const errorPage = "./about/Page-Not-Found.html";

const PATH_PART = /[^#?]*/;
const SEARCH_PART = /\?[^#]*/;

const DEBUG = true;
if (DEBUG) 
	globalThis.debugLog = console.log.bind(window.console)
else 
	globalThis.debugLog = function(){};

export function frameSearch(hash = null) {
	// return a URLSearchParams object corresponding to the search params given in the URL hash
	// representing the frame location
	
	if (hash === null)
		hash = location.hash;
	
	let subURLSearch = hash.slice(1).match(SEARCH_PART);
	if (subURLSearch)
		return new URLSearchParams(subURLSearch[0].slice(1));
	else
		return new URLSearchParams("");
}

export function setFrameSearch(params,modifyLocation = null) {
	// params: the URLSearchParams object to set the frame search to
	// modifyLocation: if provided, use this instead of the current location and return the modified URL hash
	// instead of calling replaceState.

	let url = new URL(modifyLocation || location);
	let hash = url.hash;

	if (hash.includes("?")) {
		hash = hash.replace(SEARCH_PART,"?" + params.toString());
	} else {
		let parts = hash.split("#");
		parts[1] += "?" + params.toString();
		hash = parts.join("#");
	}

	url.hash = hash;
	if (modifyLocation) {
		return url.toString();
	} else {
		url.hash = hash;
		history.replaceState(history.state,"",url);
	}
}

export function framePage() {
	// Returns the current open page

	let path = location.hash.slice(1).match(PATH_PART)[0];
	if (path)
		return path
	else
		return "homepage.html";
}

export function openLocalPage(path,query,bookmark) {
	// Open a local page in this frame
	// path is relative to pages/index.html

	let newFullUrl = new URL(location);
	newFullUrl.hash = `#${path}` + (query ? `?${query}` :"") + (bookmark ? `#${bookmark}` :"");

	history.pushState({}, "", String(newFullUrl).replace(/#keep_scroll$/,""));
	changeURL(newFullUrl.hash.slice(1));
}

function pageText(r,url) {
	if (r.ok) {
		return r.text().then((text) => {
			let redirect = text.match(/<meta[^>]*http-equiv[^>]*refresh[^>]*>/);
			if (redirect) {
				debugLog("Page contains redirect tag",redirect[0]);
				let redirectTo = redirect[0].match(/url='([^']*)'/);
				redirectTo = join(dirname(url),redirectTo[1]);
				let queryAndHash = url.match(/[#?].*/);
				if (!redirectTo.match(/[#?].*/) && queryAndHash) // Preserve query and hash if redirectTo doesn't specify them
					redirectTo += queryAndHash[0];
				debugLog("Redirecting to",redirectTo);
				return fetch(redirectTo)
					.then((r) => r.text())
					.then((text) => Promise.resolve([text,redirectTo]))
			} else
				return Promise.resolve([text,url]);
		})
	} else {
		debugLog("Page not found. Fetching",errorPage)
		return fetch(errorPage)
			.then((r) => r.text())
			.then((text) => Promise.resolve([text.replace("$PAGE$",url),errorPage]))
	}
}

export function configureLinks(frame,url) {
	// Configure links within frame to be relative to url and link to #index.html
	["href","src"].forEach((attribute) => {
		frame.querySelectorAll("["+attribute+"]").forEach((el) => {
			let attributePath = el.getAttribute(attribute);
			if (!attributePath.match(absoluteURLRegex) && !attributePath.startsWith("#")) {
				el.setAttribute(attribute,join(dirname(url),attributePath));
			};
		});
	});

	let locationNoQuery = new URL(location.href);
	locationNoQuery.search = "";
	frame.querySelectorAll("a").forEach((el) => {
		if (el.firstChild?.classList?.contains("toggle-view")) return;
			// Don't modify href links of toggle-view togglers
		let href = el.getAttribute("href");
		if (!href)
			return;
		if (href.match(absoluteURLRegex)) {
			// Switch links back to suttacentral.net if Javascript is running.
			if (href.startsWith("https://suttacentral.express/")) {
				el.href = href.replace("//suttacentral.express/","//suttacentral.net/")
			}
			return;
		}
		if (href.endsWith("#noframe")) { // Code to escape javascript frame
			el.href = el.href.replace("#noframe","");
			return;
		}

		if (href.startsWith("#")) {
			let noBookmark = decodeURIComponent(locationNoQuery.href).split("#").slice(0,2).join("#");
			el.href = noBookmark+href;
			el.addEventListener("click", (event) => {
				event.preventDefault();
				let bookmarkedItem = document.getElementById(href.slice(1));
				if (bookmarkedItem) {
					history.pushState({}, "", el.href);
					bookmarkedItem.scrollIntoView();
				}
			});
		} else {
			let url = href;
			let newLocation = new URL(locationNoQuery);
			newLocation.hash = "#" + url;
			let newFullUrl = newLocation.href.replace("#_keep_scroll","");
			el.href = newFullUrl;

			el.addEventListener("click", async (event) => {
				if (newFullUrl.includes("?_keep_query")) {
					let oldSearch = "?" + frameSearch().toString()
					newFullUrl = newFullUrl.replace("?_keep_query",oldSearch)
					url = url.replace("?_keep_query",oldSearch)
				}
				history.pushState({}, "", newFullUrl);
				event.preventDefault(); // Don't follow the href link
				await changeURL(url);
			});
		}
	});
}

async function changeURL(pUrl,scrollTo = null) {
	if (!pUrl)
		pUrl = "homepage.html";
	pUrl = decodeURIComponent(pUrl); // Other pages don't use # in search queries
	debugLog("changeURL",pUrl);
	let fileName = pUrl.match(/^.*?\.html/i)[0];
	await fetch("./" + fileName)
		.then((r) => pageText(r,pUrl))
		.then((result) => {
			let [text, resultUrl] = result;
			if (resultUrl !== pUrl) { // Update location if we were redirected to another page
				let currentLocation = new URL(location);
				currentLocation.hash = `#${resultUrl.replace(/^\.\//,"")}`;
				history.replaceState(history.state,"",currentLocation);
			}

			text = text.replaceAll(/<link[^>]*rel="stylesheet"[^>]*style\.css[^>]*>/gi,"");
			frame.innerHTML = text;

			let innerTitle = frame.querySelector("title");
			titleEl.innerHTML = innerTitle.innerHTML;
			innerTitle.remove();

			frame.querySelector("#javascript-link")?.setAttribute("style","display:none;");
			document.getElementById("noscript-style-block")?.remove();

			configureLinks(frame,resultUrl);
			loadToggleView();
			loadSearchPage(); // loadSearchPage() and loadHomepage() modify the DOM and are responsible for calling
			loadHomepage(frame); // configureLinks() and loadToggleView() on any elements they add.
			if (scrollTo && Object.hasOwn(scrollTo,"scrollX") && Object.hasOwn(scrollTo,"scrollY"))
				setInitialScroll(scrollTo);
			else {
				if (!pUrl.endsWith("#_keep_scroll")) {
					if (pUrl.includes("#"))
						setInitialScroll(pUrl.split("#")[1])
					else
						setInitialScroll({"scrollX":0, "scrollY":0});
				}
			}
		});
}

let gInitialScroll = {"scrollX":0, "scrollY":0};
export function scrollToInitialPosition() {
	if (typeof gInitialScroll === "string")
		document.getElementById(gInitialScroll)?.scrollIntoView();
	else
		window.scrollTo(gInitialScroll.scrollX,gInitialScroll.scrollY);
}

function setInitialScroll(bookmarkOrPoint) {
	// Attempt to scroll to a given location, wait, then attempt to scroll again if the user hasn't scrolled in the
	// meantime. This allows time for the page elements to fully load.
	// bookmarkOrPoint is either a string bookmark or {"scrollX":x, "scrollY":y}.

	gInitialScroll = bookmarkOrPoint;
	scrollToInitialPosition();

	// If there are many images on a page (about/02_EventSeries.html), then wait for them to load and scroll again.
	if (document.getElementsByClassName("cover").length > 1) {
		setTimeout(function(){
			scrollToInitialPosition();
		}, 1000);
	}
}

if (frame) {
	const agent = window.navigator.userAgent.toLowerCase();
	const botUsers = ['googlebot','bingbot','linkedinbot','duckduckbot','mediapartners-google','lighthouse','insights'];
	let isBotUserAgent = false;
	for (let bot of botUsers) {
		if (agent.indexOf(bot) !== -1) {
			isBotUserAgent = true;
			break;
		}
	}

	let url = new URL(location.href)
	// Skip changeURL for local files and robots loading index.html (url.hash === '')
	if (url.protocol !== "file:" && (!isBotUserAgent || url.hash)) {
		changeURL(location.hash.slice(1) || frame.dataset.url,null,true);

		addEventListener("popstate", (event) => {
			changeURL(location.hash.slice(1) || frame.dataset.url,event.state);
		});
	}
}

window.addEventListener("scrollend", (event) => {
	history.replaceState({"scrollX":window.scrollX,"scrollY":window.scrollY}, "");
});
