import posix from "./path.js";
import { loadSearchPage } from "./search.js";
import { loadHomepage } from "./homepage.js";
import { loadToggleView } from "./toggle-view.js";
import { loadFeaturedPlaylist } from "./audioPlayer.js";
const { join, dirname } = posix;
const frame = document.querySelector("div#frame");
const titleEl = document.querySelector("title");
const absoluteURLRegex = "^(//|[a-z+]+:)"
const errorPage = "./about/Page-Not-Found.html"

const SEARCH_PART = /\?[^#]*/

export function frameSearch(hash = null) {
	// return a URLSearchParams object corresponding to the search params given in the URL hash
	// representing the frame location
	
	if (hash == null)
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

function pageText(r,url) {
	if (r.ok) {
		return r.text().then((text) => Promise.resolve([text,url]))
	} else {
		console.log("Page not found. Fetching",errorPage)
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
		if (!href || href.match(absoluteURLRegex)) return;
		if (href.endsWith("#noscript")) { // Code to escape javascript
			el.href = el.href.replace("#noscript","");
			return;
		}

		if (href.startsWith("#")) {
			let noBookmark = decodeURIComponent(locationNoQuery.href).split("#").slice(0,2).join("#");
			el.href = noBookmark+href;
			el.addEventListener("click", () => {
				history.pushState({}, "", el.href);
				document.getElementById(href.slice(1)).scrollIntoView();
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
	pUrl = decodeURIComponent(pUrl);
	console.log("changeURL",pUrl);
	await fetch("./" + pUrl)
		.then((r) => pageText(r,pUrl))
		.then((result) => {
			let [text, resultUrl] = result;
			text = text.replaceAll(/<link[^>]*rel="stylesheet"[^>]*style\.css[^>]*>/gi,"");
			frame.innerHTML = text;

			let innerTitle = frame.querySelector("title");
			titleEl.innerHTML = innerTitle.innerHTML;
			innerTitle.remove();

			frame.querySelector("#javascript-link")?.setAttribute("style","display:none;");

			configureLinks(frame,resultUrl);
			loadToggleView();
			loadSearchPage(); // loadSearchPage() and loadHomepage() modify the DOM and are responsible for calling
			loadHomepage(); // configureLinks() and loadToggleView() on any elements they add.
			loadFeaturedPlaylist();
			if (scrollTo && Object.hasOwn(scrollTo,"scrollX") && Object.hasOwn(scrollTo,"scrollY"))
				window.scrollTo(scrollTo.scrollX,scrollTo.scrollY)
			else {
				if (!pUrl.endsWith("#_keep_scroll")) {
					if (pUrl.includes("#"))
						delayedScroll(pUrl.split("#")[1])
					else
						window.scrollTo(0, 0);
				}
			}
		});
}

function delayedScroll(bookmark) {
	document.getElementById(bookmark)?.scrollIntoView();
	// If there are many images on a page (about/02_EventSeries.html), then wait for them to load and scroll again.
	if (document.getElementsByClassName("cover").length > 1) {
		setTimeout(function(){
			document.getElementById(bookmark)?.scrollIntoView();
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
	// Skip changeURL for local files and robots loading index.html (url.hash == '')
	if (url.protocol != "file:" && (!isBotUserAgent || url.hash)) {
		changeURL(location.hash.slice(1) || frame.dataset.url);

		addEventListener("popstate", (event) => {
			changeURL(location.hash.slice(1) || frame.dataset.url,event.state);
		});
	}
}

window.addEventListener("scrollend", (event) => {
	history.replaceState({"scrollX":window.scrollX,"scrollY":window.scrollY}, "");
});
