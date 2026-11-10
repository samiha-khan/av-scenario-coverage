/* ============================================================================
 *  PERSONALIZE HERE  — everything you might want to change lives in this block.
 * ========================================================================== */
const BIRTHDAY_CONFIG = {
  // His name. Used in the headline ("Happy Birthday, Utshab!") and the countdown.
  // Leave it as "" to fall back to "Happy Birthday, love!".
  name: "Utshab",

  // Your message, shown right under the headline on his birthday.
  // Use "\n\n" between paragraphs if you want more than one.
  message: "Happy Birthday Love!",

  // Sign-off shown under the message. Leave "" to hide it.
  signoff: "Hoping to celebrate this day together for eternity.",

  // Optional photos. Drop image files into the photos/ folder next to this file and list them
  // here like "photos/us.jpg", or paste full https:// image links.
  // Each entry can be just a path, or { src, caption } to write something
  // under the polaroid. Leave the list empty ([]) to hide the photo strip.
  photos: [
    { src: "photos/utshab-birthday-cake.jpg", caption: "birthday boy" },
    { src: "photos/utshab-library.jpg", caption: "super cute and kissable" },
    { src: "photos/us-central-park.jpg", caption: "matching, on purpose" },
    { src: "photos/us-gym-selfie.jpg", caption: "a random click" },
    // "photos/us-at-the-park.jpg",
    // { src: "https://example.com/our-trip.jpg", caption: "that trip" },
  ],

  // The "reasons I love you" cards. Mix sweet and silly — add, remove, or
  // reorder as many as you like. A reason can be plain text, or
  // { text, photo } to flip open onto a photo with the text as its caption.
  reasons: [
    "Being with you itself is a festival.",
    "Your hugs are my favorite place in the whole world.",
    "You always manage to make me happy.",
    "You're my favorite person. It's not even close.",
    // Example of a card that flips open onto a photo:
    // { text: "Too kissable.", photo: "photos/utshab-library.jpg" },
  ],

  // Start the birthday with a sealed envelope he taps to open. The letter
  // inside shows the message and sign-off above. Set to false to skip it.
  openAsLetter: true,
  letterGreeting: "Dear Utshab,",   // first line inside the letter
  letterFrom: "yours, always",      // last line inside the letter ("" to hide)

  // What the cake says after he blows out the candles.
  wishMessage: "Wish made. I won't ask what it was. (I will absolutely ask.)",

  // Birthday and time zone — already set for November 10 in New York.
  month: 11,
  day: 10,
  timeZone: "America/New_York",
};
/* ========================================================================== */

(() => {
  const cfg = BIRTHDAY_CONFIG;
  const $ = (id) => document.getElementById(id);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- optional preview controls (handy for testing) ----------
   *   ?view=countdown   force the countdown view
   *   ?view=celebrate   force the celebration view
   *   ?now=<ISO date>   pretend the current time is this instant, e.g.
   *                     ?now=2026-11-09T23:59:50-05:00 to watch the switch happen
   */
  const params = new URLSearchParams(location.search);
  const forcedView = params.get("view");
  let clockOffset = 0;
  if (params.get("now")) {
    const simulated = Date.parse(params.get("now"));
    if (!Number.isNaN(simulated)) clockOffset = simulated - Date.now();
  }
  const now = () => new Date(Date.now() + clockOffset);

  /* ---------- time zone helpers ---------- */
  const partsFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: cfg.timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
  });

  function zoneParts(date) {
    const out = {};
    for (const p of partsFormatter.formatToParts(date)) {
      if (p.type !== "literal") out[p.type] = Number(p.value);
    }
    return out;
  }

  // The UTC instant at which it becomes 00:00 on (year, month, day) in cfg.timeZone.
  function zonedMidnightUtc(year, month, day) {
    const wanted = Date.UTC(year, month - 1, day, 0, 0, 0);
    let guess = wanted;
    for (let i = 0; i < 3; i++) {
      const p = zoneParts(new Date(guess));
      const asUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
      const diff = wanted - asUtc;
      if (diff === 0) break;
      guess += diff;
    }
    return guess;
  }

  function isBirthdayNow(date) {
    const p = zoneParts(date);
    return p.month === cfg.month && p.day === cfg.day;
  }

  function nextBirthdayUtc(date) {
    const p = zoneParts(date);
    let year = p.year;
    if (p.month > cfg.month || (p.month === cfg.month && p.day > cfg.day)) year += 1;
    return zonedMidnightUtc(year, cfg.month, cfg.day);
  }

  const clockFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: cfg.timeZone,
    hour: "numeric",
    minute: "2-digit",
  });

  const monthName = new Intl.DateTimeFormat("en-US", { month: "long", timeZone: "UTC" }).format(
    new Date(Date.UTC(2000, cfg.month - 1, 1))
  );

  /* ---------- text ---------- */
  const name = (cfg.name || "").trim();
  const headlineText = name ? `Happy Birthday, ${name}!` : "Happy Birthday, love!";
  const possessive = name ? `${name}'s` : "your";

  document.title = headlineText;
  $("headline").textContent = headlineText;
  $("countdown-name").textContent = possessive;
  $("countdown-date").textContent = `${monthName} ${cfg.day}`;
  $("celebration-eyebrow").textContent = `${monthName} ${cfg.day} · New York City`;
  $("signoff").textContent = cfg.signoff || "";

  const messageEl = $("message");
  messageEl.replaceChildren(
    ...String(cfg.message || "")
      .split(/\n\s*\n/)
      .filter((s) => s.trim())
      .map((text) => {
        const p = document.createElement("p");
        p.textContent = text.trim();
        return p;
      })
  );

  const photosEl = $("photos");
  const photos = (cfg.photos || [])
    .map((p) => (typeof p === "string" ? { src: p, caption: "" } : p))
    .filter((p) => p && p.src);
  if (photos.length) {
    photosEl.hidden = false;
    photosEl.classList.toggle("single", photos.length === 1);

    const track = document.createElement("div");
    track.className = "carousel-track";
    track.setAttribute("aria-label", "Photos");
    photos.forEach(({ src, caption }, i) => {
      const slide = document.createElement("div");
      slide.className = "slide";
      const fig = document.createElement("figure");
      fig.className = "polaroid";
      fig.style.setProperty("--tilt", `${(i % 2 ? 1 : -1) * 2}deg`);
      const img = document.createElement("img");
      img.src = src;
      img.alt = caption || "";
      img.loading = i === 0 ? "eager" : "lazy";
      img.draggable = false;
      fig.appendChild(img);
      if (caption) {
        const cap = document.createElement("figcaption");
        cap.textContent = caption;
        fig.appendChild(cap);
      }
      slide.appendChild(fig);
      track.appendChild(slide);
    });
    photosEl.appendChild(track);

    if (photos.length > 1) {
      const dots = document.createElement("div");
      dots.className = "carousel-dots";
      photos.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "dot";
        dot.setAttribute("aria-label", `Photo ${i + 1} of ${photos.length}`);
        dot.addEventListener("click", () => goTo(i, true));
        dots.appendChild(dot);
      });
      const prev = document.createElement("button");
      prev.type = "button";
      prev.className = "carousel-arrow prev";
      prev.setAttribute("aria-label", "Previous photo");
      prev.innerHTML = "&#8249;";
      const next = document.createElement("button");
      next.type = "button";
      next.className = "carousel-arrow next";
      next.setAttribute("aria-label", "Next photo");
      next.innerHTML = "&#8250;";
      prev.addEventListener("click", () => goTo(current - 1, true));
      next.addEventListener("click", () => goTo(current + 1, true));
      photosEl.append(prev, next, dots);

      let current = 0;
      let autoTimer = null;
      const dotEls = [...dots.children];

      const setActive = (i) => {
        current = i;
        dotEls.forEach((d, j) => d.classList.toggle("active", j === i));
      };

      function goTo(i, byUser) {
        const n = photos.length;
        const idx = ((i % n) + n) % n;
        track.scrollTo({ left: idx * track.clientWidth, behavior: reducedMotion ? "auto" : "smooth" });
        setActive(idx);
        if (byUser) pauseAuto();
      }

      track.addEventListener("scroll", () => {
        const idx = Math.round(track.scrollLeft / Math.max(1, track.clientWidth));
        if (idx !== current) setActive(Math.min(photos.length - 1, Math.max(0, idx)));
      }, { passive: true });

      function startAuto() {
        if (reducedMotion) return;
        clearInterval(autoTimer);
        autoTimer = setInterval(() => goTo(current + 1, false), 4500);
      }
      function pauseAuto() {
        clearInterval(autoTimer);
        autoTimer = setTimeout(startAuto, 12000);
      }
      track.addEventListener("pointerdown", pauseAuto, { passive: true });
      track.addEventListener("touchstart", pauseAuto, { passive: true });
      setActive(0);
      startAuto();
    }
  }

  /* ---------- balloons ---------- */
  const balloonColors = ["#ff7a8a", "#f6c667", "#ffb38a", "#c98bff", "#7fd1c9", "#ff9ecb"];
  function spawnBalloons(count) {
    const host = $("balloons");
    host.replaceChildren();
    if (reducedMotion) return;
    for (let i = 0; i < count; i++) {
      const b = document.createElement("div");
      b.className = "balloon";
      // keep the middle of the screen clear so the headline stays readable
      const side = i % 2 ? 70 + Math.random() * 26 : Math.random() * 26;
      b.style.left = `${side}%`;
      b.style.setProperty("--color", balloonColors[i % balloonColors.length]);
      b.style.setProperty("--size", `${40 + Math.random() * 36}px`);
      b.style.setProperty("--duration", `${16 + Math.random() * 14}s`);
      b.style.setProperty("--delay", `${-Math.random() * 24}s`);
      b.style.setProperty("--drift", `${(Math.random() > 0.5 ? 1 : -1) * (20 + Math.random() * 40)}px`);
      host.appendChild(b);
    }
  }

  /* ---------- confetti ---------- */
  const canvas = $("confetti");
  const ctx = canvas.getContext("2d");
  const pieces = [];
  const confettiColors = ["#ff7a8a", "#f6c667", "#ffb38a", "#fff4e6", "#c98bff", "#7fd1c9"];
  let raf = null;
  let dpr = 1;

  function resizeCanvas() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.floor(innerWidth * dpr);
    canvas.height = Math.floor(innerHeight * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  addEventListener("resize", resizeCanvas);
  resizeCanvas();

  function burst(count, originX = 0.5, originY = 0.35, spread = 1) {
    if (reducedMotion) return;
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = (3 + Math.random() * 9) * spread;
      pieces.push({
        x: innerWidth * originX,
        y: innerHeight * originY,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 4,
        w: 6 + Math.random() * 6,
        h: 8 + Math.random() * 8,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.3,
        color: confettiColors[(Math.random() * confettiColors.length) | 0],
        life: 160 + Math.random() * 100,
        shape: Math.random() > 0.8 ? "heart" : "rect",
      });
    }
    if (!raf) raf = requestAnimationFrame(tick);
  }

  function drizzle(count) {
    if (reducedMotion) return;
    for (let i = 0; i < count; i++) {
      pieces.push({
        x: Math.random() * innerWidth,
        y: -20 - Math.random() * 60,
        vx: (Math.random() - 0.5) * 1.5,
        vy: 1 + Math.random() * 2,
        w: 5 + Math.random() * 6,
        h: 7 + Math.random() * 8,
        rot: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.2,
        color: confettiColors[(Math.random() * confettiColors.length) | 0],
        life: 400 + Math.random() * 200,
        shape: Math.random() > 0.85 ? "heart" : "rect",
      });
    }
    if (!raf) raf = requestAnimationFrame(tick);
  }

  function drawHeart(size) {
    ctx.beginPath();
    const s = size / 2;
    ctx.moveTo(0, s * 0.6);
    ctx.bezierCurveTo(-s * 1.4, -s * 0.5, -s * 0.5, -s * 1.3, 0, -s * 0.4);
    ctx.bezierCurveTo(s * 0.5, -s * 1.3, s * 1.4, -s * 0.5, 0, s * 0.6);
    ctx.fill();
  }

  function tick() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (let i = pieces.length - 1; i >= 0; i--) {
      const p = pieces[i];
      p.vy += 0.12;
      p.vx *= 0.99;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vr;
      p.life -= 1;
      if (p.life <= 0 || p.y > innerHeight + 40) {
        pieces.splice(i, 1);
        continue;
      }
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.globalAlpha = Math.min(1, p.life / 60);
      ctx.fillStyle = p.color;
      if (p.shape === "heart") drawHeart(p.w * 1.6);
      else ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.rot)));
      ctx.restore();
    }
    raf = pieces.length ? requestAnimationFrame(tick) : null;
  }

  let drizzleTimer = null;
  function startCelebrationConfetti() {
    burst(220, 0.5, 0.4);
    setTimeout(() => burst(120, 0.2, 0.5), 350);
    setTimeout(() => burst(120, 0.8, 0.5), 650);
    clearInterval(drizzleTimer);
    drizzleTimer = setInterval(() => drizzle(6), 500);
    setTimeout(() => clearInterval(drizzleTimer), 14000);
  }

  /* ---------- cake ---------- */
  const CANDLE_COUNT = 5;
  const candlesEl = $("candles");
  const cakeEl = $("cake");
  const cakeCaption = $("cake-caption");
  const relightBtn = $("relight");
  let candlesOut = false;

  function buildCandles() {
    candlesEl.replaceChildren();
    for (let i = 0; i < CANDLE_COUNT; i++) {
      const c = document.createElement("div");
      c.className = "candle";
      c.style.setProperty("--i", i);
      c.innerHTML = '<div class="flame"></div><div class="smoke"></div>';
      candlesEl.appendChild(c);
    }
  }
  buildCandles();

  function blowOut() {
    if (candlesOut) return;
    candlesOut = true;
    cakeEl.classList.add("out");
    cakeCaption.textContent = cfg.wishMessage;
    relightBtn.hidden = false;
    const r = cakeEl.getBoundingClientRect();
    burst(140, (r.left + r.width / 2) / innerWidth, (r.top + r.height * 0.3) / innerHeight, 0.8);
  }

  function relight() {
    candlesOut = false;
    cakeEl.classList.remove("out");
    buildCandles();
    cakeCaption.textContent = "Relit. Go again, birthday boy.";
    relightBtn.hidden = true;
  }

  cakeEl.addEventListener("click", blowOut);
  relightBtn.addEventListener("click", relight);

  /* ---------- reasons ---------- */
  const reasonsEl = $("reasons");
  const stickers = ["💌", "🍟", "🍕", "🫶", "🎈", "🌙", "☕", "🧸", "🌟", "🎂"];
  (cfg.reasons || []).forEach((reason, i) => {
    const { text, photo } = typeof reason === "string" ? { text: reason } : reason;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "reason" + (photo ? " has-photo" : "");
    card.setAttribute("aria-expanded", "false");
    card.style.setProperty("--tilt", `${((i % 3) - 1) * 1.6}deg`);
    const front = document.createElement("span");
    front.className = "reason-front";
    front.innerHTML = `<span class="reason-sticker" aria-hidden="true">${stickers[i % stickers.length]}</span><span class="reason-num">No. ${i + 1}</span>`;
    const back = document.createElement("span");
    back.className = "reason-back";
    if (photo) {
      const img = document.createElement("img");
      img.src = photo;
      img.alt = "";
      img.loading = "lazy";
      const cap = document.createElement("span");
      cap.className = "reason-caption";
      cap.textContent = text;
      back.append(img, cap);
    } else {
      back.textContent = text;
    }
    card.append(front, back);
    card.addEventListener("click", () => {
      const open = card.classList.toggle("open");
      card.setAttribute("aria-expanded", String(open));
      if (open) {
        const r = card.getBoundingClientRect();
        burst(18, (r.left + r.width / 2) / innerWidth, (r.top + r.height / 2) / innerHeight, 0.4);
      }
    });
    reasonsEl.appendChild(card);
  });

  /* ---------- hug dispenser ---------- */
  const hugLines = [
    "Hug delivered.",
    "Another one? Okay, twist my arm.",
    "This one's extra tight.",
    "Hug #{n}. The supply is infinite, by the way.",
    "Warning: dangerously huggable.",
    "Still here. Still hugging.",
  ];
  let hugs = 0;
  const hugOverlay = $("hug-overlay");
  const hugText = $("hug-text");
  const hugCount = $("hug-count");
  let hugTimer = null;

  $("hug-btn").addEventListener("click", () => {
    hugs += 1;
    const line = hugLines[Math.min(hugs - 1, hugLines.length - 1)].replace("{n}", hugs);
    hugText.textContent = line;
    hugOverlay.classList.add("show");
    hugOverlay.setAttribute("aria-hidden", "false");
    burst(60, 0.5, 0.5, 0.7);
    hugCount.textContent = hugs === 1 ? "1 hug dispensed" : `${hugs} hugs dispensed`;
    clearTimeout(hugTimer);
    hugTimer = setTimeout(() => {
      hugOverlay.classList.remove("show");
      hugOverlay.setAttribute("aria-hidden", "true");
    }, 1800);
  });
  hugOverlay.addEventListener("click", () => {
    clearTimeout(hugTimer);
    hugOverlay.classList.remove("show");
    hugOverlay.setAttribute("aria-hidden", "true");
  });

  /* ---------- the quiz with the uncatchable "No" ---------- */
  const noBtn = $("no-btn");
  const yesBtn = $("yes-btn");
  const quizCard = $("quiz-card");
  const quizNote = $("quiz-note");
  const dodgeLines = [
    "Nope.",
    "Too slow.",
    "Nice try.",
    "That button is shy.",
    "Think about it.",
    "Really?",
    "The other one. 😌",
  ];
  let dodges = 0;

  function dodge() {
    dodges += 1;
    noBtn.classList.add("dodging");
    const cardRect = quizCard.getBoundingClientRect();
    const btnRect = noBtn.getBoundingClientRect();
    const maxX = Math.max(0, cardRect.width - btnRect.width - 24);
    const maxY = Math.max(0, cardRect.height - btnRect.height - 24);
    noBtn.style.left = `${12 + Math.random() * maxX}px`;
    noBtn.style.top = `${12 + Math.random() * maxY}px`;
    noBtn.style.transform = `rotate(${(Math.random() - 0.5) * 20}deg) scale(${Math.max(0.6, 1 - dodges * 0.05)})`;
    quizNote.textContent = dodgeLines[Math.min(dodges - 1, dodgeLines.length - 1)];
    if (dodges >= 6) {
      yesBtn.textContent = "Yes (obviously)";
      yesBtn.classList.add("grow");
    }
  }
  noBtn.addEventListener("pointerenter", dodge);
  noBtn.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    dodge();
  });
  noBtn.addEventListener("click", (e) => {
    e.preventDefault();
    dodge();
  });
  noBtn.addEventListener("focus", dodge);

  yesBtn.addEventListener("click", () => {
    $("quiz-question").textContent = "Correct. There was only one right answer.";
    $("quiz-buttons").hidden = true;
    quizNote.textContent = "Thank you for your honesty. Please collect your hug above. 💛";
    const r = quizCard.getBoundingClientRect();
    burst(120, (r.left + r.width / 2) / innerWidth, (r.top + r.height / 2) / innerHeight, 0.7);
  });

  /* ---------- the letter ---------- */
  const letterOverlay = $("letter-overlay");
  const envelope = $("envelope");
  let letterOpened = false;

  $("letter-to").textContent = cfg.letterGreeting || (name ? `Dear ${name},` : "Dear you,");
  $("letter-from").textContent = cfg.letterFrom || "";
  $("letter-body").replaceChildren(
    ...[cfg.message, cfg.signoff]
      .filter((s) => s && s.trim())
      .map((text) => {
        const p = document.createElement("p");
        p.textContent = text.trim();
        return p;
      })
  );

  function showLetter(onDone) {
    letterOverlay.hidden = false;
    document.body.classList.add("reading-letter");
    const open = () => {
      if (letterOpened) return;
      letterOpened = true;
      envelope.classList.add("open");
      $("letter-hint").textContent = "";
      const delay = reducedMotion ? 600 : 3400;
      setTimeout(() => {
        letterOverlay.classList.add("away");
        document.body.classList.remove("reading-letter");
        setTimeout(() => {
          letterOverlay.hidden = true;
          onDone();
        }, reducedMotion ? 50 : 700);
      }, delay);
    };
    envelope.addEventListener("click", open, { once: true });
  }

  /* ---------- views ---------- */
  const countdownView = $("countdown-view");
  const celebrationView = $("celebration-view");
  const extras = $("extras");
  let currentView = null;
  let countdownTimer = null;

  function showCountdown() {
    if (currentView === "countdown") return;
    currentView = "countdown";
    celebrationView.hidden = true;
    extras.hidden = true;
    countdownView.hidden = false;
    document.body.classList.remove("celebrating");
    spawnBalloons(6);
    updateCountdown();
    clearInterval(countdownTimer);
    countdownTimer = setInterval(updateCountdown, 250);
  }

  function revealCelebration() {
    celebrationView.hidden = false;
    extras.hidden = false;
    document.body.classList.add("celebrating");
    spawnBalloons(14);
    startCelebrationConfetti();
  }

  function showCelebration({ animate }) {
    if (currentView === "celebration") return;
    currentView = "celebration";
    clearInterval(countdownTimer);
    countdownView.hidden = true;
    if (cfg.openAsLetter && !params.has("noletter")) {
      spawnBalloons(0);
      showLetter(revealCelebration);
    } else if (animate) {
      revealCelebration();
    } else {
      setTimeout(revealCelebration, 300);
    }
  }

  const pad = (n) => String(n).padStart(2, "0");

  function updateCountdown() {
    const current = now();
    if (!forcedView && isBirthdayNow(current)) {
      showCelebration({ animate: true });
      return;
    }
    const target = nextBirthdayUtc(current);
    const remaining = Math.max(0, target - current.getTime());
    const totalSeconds = Math.floor(remaining / 1000);
    $("days").textContent = pad(Math.floor(totalSeconds / 86400));
    $("hours").textContent = pad(Math.floor((totalSeconds % 86400) / 3600));
    $("minutes").textContent = pad(Math.floor((totalSeconds % 3600) / 60));
    $("seconds").textContent = pad(totalSeconds % 60);
    $("ny-time").textContent = clockFormatter.format(current);
  }

  /* ---------- boot ---------- */
  if (forcedView === "celebrate" || forcedView === "celebration") {
    showCelebration({ animate: false });
  } else if (forcedView === "countdown") {
    showCountdown();
  } else if (isBirthdayNow(now())) {
    showCelebration({ animate: false });
  } else {
    showCountdown();
  }
})();
