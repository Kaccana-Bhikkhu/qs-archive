const css = `
	.wrapper {
		height: 40px;
		width: max-content;

		display: grid;
		grid-template-columns: 40px 50px 40px;
		grid-template-rows: 1fr;
		grid-column-gap: 5px;
		grid-row-gap: 0px; 
		align-items: center;
	}

	button.play {
		grid-area: 1 / 1 / 3 / 2;
		
		height: 40px;
		width: 40px;
		border-radius: 0.4rem;
		border: none;
		margin-right: 7px;

		background: url(assets/play.svg) center no-repeat;
		background-size: 40%;
		background-color: #f0f0f0;
		cursor: pointer;
	}

	a {
		opacity: 0.5;
		color: #0088cc !important;
		transition: opacity 200ms ease-out;
		font-size: 0.9em;

		background: url(assets/download.svg) center no-repeat;
		background-size: 40%;
		width: 40px;
		height: 40px;
	}

	a:hover {
		opacity: 1;
	}
`;
const time = (sec) =>
	`${Math.floor(sec / 60)}:${(sec % 60).toString().padStart(2, "0")}`;

class AudioChip extends HTMLElement {
	/** @type {HTMLAudioElement} */
	audio;
	#titleWithLink;

	constructor() {
		super();

		this.attachShadow({ mode: "open" });
	}

	setAttribute(key,value) {
		super.setAttribute(key,value);
		if (key === "src") {
			this.audio.src = value; // Change playing audio
			if (this.dataset.duration === null)
				this.audio.load();
			this.shadowRoot.querySelector("a").href = value; // Change the file to download
		}
	}

	connectedCallback() {
		let src = this.getAttribute("src");
		this.audio = new Audio(src);
		let loadAudio = this.dataset.duration === null;
		if (loadAudio)
			this.audio.load()
		else
			this.audio.preload = "none";

		const wrapper = document.createElement("div");
		wrapper.classList.add("wrapper");
		const button = document.createElement("button");
		button.classList.add("play");

		if (this.dataset.titleLink) {
			this.#titleWithLink = `<a href="#${this.dataset.titleLink}">${this.title}</a>`
		} else {
			this.#titleWithLink = this.title;
		}

		button.addEventListener("click", this.play.bind(this, false));

		const timeLabel = document.createElement("span");
		if (loadAudio) timeLabel.innerText = "...";
		else timeLabel.innerHTML = `<i>${time(this.dataset.duration)}</i>`;
		this.audio.addEventListener("canplaythrough", () => {
			let duration = Math.round(this.audio.duration);
			timeLabel.innerText = time(duration);
		});

		const download = document.createElement("a");
		download.title = "Download";
		download.href = src;
		if (this.dataset.downloadAs)
			download.download = this.dataset.downloadAs;
		else
			download.download = this.title + ".mp3";
		// download.target = "_blank";

		const style = document.createElement("style");
		style.innerText = css;

		wrapper.append(button, timeLabel, download);
		this.shadowRoot.append(style, wrapper);
	}

	play(onPlaylist = false) {
		if (this.audio.readyState >= 3) {
			debugLog("audio already loaded; begin playing");
			playAudio(this.#titleWithLink, this.audio, onPlaylist);
		} else {
			this.audio.addEventListener(
				"canplay",
				(() => {
					debugLog("canplay event triggered; begin playing");
					playAudio(this.#titleWithLink, this.audio, onPlaylist);
				}),
				{ once: true },
			);
			this.audio.load();
			debugLog("waiting for audio loading");
		}
	}
}

customElements.define("audio-chip", AudioChip);
