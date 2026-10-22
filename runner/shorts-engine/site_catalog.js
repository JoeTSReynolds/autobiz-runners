const search = document.querySelector("#catalog-search");
const cards = [...document.querySelectorAll(".video-card")];
const empty = document.querySelector("#search-empty");

search?.addEventListener("input", () => {
  const query = search.value.trim().toLocaleLowerCase();
  let visible = 0;
  for (const card of cards) {
    const matches = card.dataset.search.includes(query);
    card.hidden = !matches;
    if (matches) visible += 1;
  }
  empty.hidden = visible > 0 || cards.length === 0;
});
