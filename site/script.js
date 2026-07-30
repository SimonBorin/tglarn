const versionNodes = document.querySelectorAll(".js-version, #latest-version");

async function refreshVersion() {
  try {
    const response = await fetch("https://api.github.com/repos/SimonBorin/tglarn/tags?per_page=30");
    if (!response.ok) return;

    const tags = await response.json();
    const versions = tags
      .map(({ name }) => /^v?(\d+)\.(\d+)\.(\d+)$/.exec(name))
      .filter(Boolean)
      .map((match) => ({
        label: `v${match[1]}.${match[2]}.${match[3]}`,
        parts: match.slice(1).map(Number),
      }))
      .sort((left, right) => {
        for (let index = 0; index < 3; index += 1) {
          if (left.parts[index] !== right.parts[index]) {
            return right.parts[index] - left.parts[index];
          }
        }
        return 0;
      });

    if (versions.length > 0) {
      versionNodes.forEach((node) => {
        node.textContent = versions[0].label;
      });
    }
  } catch {
    // The static fallback remains visible when the GitHub API is unavailable.
  }
}

const lightbox = document.querySelector("#lightbox");
const lightboxImage = lightbox?.querySelector("img");
const closeLightbox = lightbox?.querySelector(".lightbox-close");

document.querySelectorAll(".shot-open").forEach((button) => {
  button.addEventListener("click", () => {
    if (!lightbox || !lightboxImage) return;
    lightboxImage.src = button.dataset.image;
    lightboxImage.alt = button.dataset.alt;
    lightbox.showModal();
  });
});

closeLightbox?.addEventListener("click", () => lightbox.close());
lightbox?.addEventListener("click", (event) => {
  if (event.target === lightbox) lightbox.close();
});

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (reducedMotion || !("IntersectionObserver" in window)) {
  document.querySelectorAll(".reveal").forEach((node) => node.classList.add("is-visible"));
} else {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "0px 0px -8%", threshold: 0.08 },
  );
  document.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
}

refreshVersion();
