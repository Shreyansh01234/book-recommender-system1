"use client";

import {
  ArrowDownRight,
  ArrowRight,
  BookOpen,
  Bookmark,
  Check,
  ChevronDown,
  Compass,
  Heart,
  Library,
  LoaderCircle,
  Search,
  Sparkles,
  Star,
  UserRound,
  WandSparkles,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const GENRE_HINT = "Genre labels are estimates from book titles, not publisher-supplied metadata.";

type Book = {
  id: string;
  title: string;
  author: string;
  publisher: string;
  published_year: number | null;
  cover_url: string;
  genre_tags: string[];
  rating_count: number;
  average_rating: number;
};

type Reader = {
  id: string;
  display_name: string;
  preferred_genres: string[];
  preferred_authors: string[];
};

type Rating = { id: number; book_id: string; value: number; created_at: string };
type Recommendation = { book: Book; score: number; reasons: string[]; model_mix: string };
type Facets = { genres: string[]; authors: string[] };
type View = "discover" | "for-you" | "shelf";

class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // Keep the HTTP status as the useful error when the response is not JSON.
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

function Cover({ book }: { book: Book }) {
  const [unavailable, setUnavailable] = useState(!book.cover_url);
  return (
    <div className={`book-cover${unavailable ? " book-cover--empty" : ""}`}>
      {unavailable ? (
        <div className="cover-fallback">
          <BookOpen size={27} strokeWidth={1.4} />
          <span>{book.title.slice(0, 34)}</span>
        </div>
      ) : (
        // The source catalog uses remote cover URLs; regular img avoids a hard-coded host allowlist.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={book.cover_url} alt={`Cover of ${book.title}`} loading="lazy" onError={() => setUnavailable(true)} />
      )}
      {book.average_rating > 0 && (
        <span className="cover-rating">
          <Star size={12} fill="currentColor" /> {book.average_rating.toFixed(1)}
        </span>
      )}
    </div>
  );
}

function BookCard({
  book,
  recommendation,
  currentRating,
  onRate,
  saving,
}: {
  book: Book;
  recommendation?: Recommendation;
  currentRating?: number;
  onRate: (book: Book, rating: number) => void;
  saving: boolean;
}) {
  return (
    <article className="book-card">
      <Cover book={book} />
      <div className="book-card__body">
        <div className="book-tags">
          {(book.genre_tags.slice(0, 2).length ? book.genre_tags.slice(0, 2) : ["New to Folio"]).map((tag) => (
            <span className="book-tag" key={tag}>{tag}</span>
          ))}
        </div>
        <h3 title={book.title}>{book.title}</h3>
        <p className="book-author">{book.author}</p>
        {recommendation && (
          <div className="why-card">
            <span><Sparkles size={13} /> WHY IT FITS</span>
            <p>{recommendation.reasons.join(" · ")}</p>
          </div>
        )}
        <div className="card-bottom">
          <div className="rating-control" aria-label={`Rate ${book.title}`}>
            {[1, 2, 3, 4, 5].map((rating) => (
              <button
                type="button"
                key={rating}
                className={rating <= (currentRating ?? 0) ? "rating-star is-selected" : "rating-star"}
                aria-label={`Rate ${rating} out of 5`}
                disabled={saving}
                onClick={() => onRate(book, rating)}
              >
                <Star size={15} fill={rating <= (currentRating ?? 0) ? "currentColor" : "none"} />
              </button>
            ))}
          </div>
          <span className="rate-hint">{saving ? "Saving…" : currentRating ? "Your rating" : "Rate it"}</span>
        </div>
      </div>
    </article>
  );
}

export default function Home() {
  const [reader, setReader] = useState<Reader | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [history, setHistory] = useState<Rating[]>([]);
  const [facets, setFacets] = useState<Facets>({ genres: [], authors: [] });
  const [activeView, setActiveView] = useState<View>("discover");
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("");
  const [author, setAuthor] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingRating, setSavingRating] = useState<string | null>(null);
  const [savingPreferences, setSavingPreferences] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [authorPreference, setAuthorPreference] = useState("");
  const [pendingGenres, setPendingGenres] = useState<string[]>([]);

  const historyByBook = useMemo(
    () => new Map(history.map((rating) => [rating.book_id, rating.value])),
    [history],
  );

  const loadRecommendations = useCallback(async (userId: string) => {
    const data = await request<Recommendation[]>(`/recommendations?user_id=${encodeURIComponent(userId)}&limit=12`);
    setRecommendations(data);
  }, []);

  const loadHistory = useCallback(async (userId: string) => {
    setHistory(await request<Rating[]>(`/users/${encodeURIComponent(userId)}/history`));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      try {
        let userId = localStorage.getItem("folio-reader-id");
        let profile: Reader | null = null;
        if (userId) {
          try {
            profile = await request<Reader>(`/users/${encodeURIComponent(userId)}`);
          } catch (reason) {
            if (!(reason instanceof ApiError) || reason.status !== 404) throw reason;
          }
        }
        if (!profile) {
          userId = crypto.randomUUID();
          localStorage.setItem("folio-reader-id", userId);
          profile = await request<Reader>("/users", {
            method: "POST",
            body: JSON.stringify({ id: userId, display_name: "Reader" }),
          });
        }
        const [catalog, allFacets, ratings, picks] = await Promise.all([
          request<Book[]>("/books?limit=36"),
          request<Facets>("/books/facets"),
          request<Rating[]>(`/users/${encodeURIComponent(profile.id)}/history`),
          request<Recommendation[]>(`/recommendations?user_id=${encodeURIComponent(profile.id)}&limit=12`),
        ]);
        if (cancelled) return;
        setReader(profile);
        setPendingGenres(profile.preferred_genres);
        setBooks(catalog);
        setFacets(allFacets);
        setHistory(ratings);
        setRecommendations(picks);
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "The Folio API could not be reached.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void initialize();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!reader) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      const params = new URLSearchParams({ limit: "36" });
      if (query.trim()) params.set("query", query.trim());
      if (genre) params.set("genre", genre);
      if (author.trim()) params.set("author", author.trim());
      try {
        setBooks(await request<Book[]>(`/books?${params}`, { signal: controller.signal }));
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Catalog search failed.");
      }
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [reader, query, genre, author]);

  async function rateBook(book: Book, value: number) {
    if (!reader) return;
    setSavingRating(book.id);
    setError("");
    setSuccess("");
    try {
      await request<Rating>("/ratings", {
        method: "POST",
        body: JSON.stringify({ user_id: reader.id, book_id: book.id, value }),
      });
      await Promise.all([loadHistory(reader.id), loadRecommendations(reader.id)]);
      setSuccess(`Your ${value}-star rating for “${book.title}” is saved.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your rating.");
    } finally {
      setSavingRating(null);
    }
  }

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reader) return;
    setSavingPreferences(true);
    setError("");
    setSuccess("");
    const authors = authorPreference.trim()
      ? [...new Set([...reader.preferred_authors, authorPreference.trim()])]
      : reader.preferred_authors;
    try {
      const updated = await request<Reader>(`/users/${encodeURIComponent(reader.id)}/preferences`, {
        method: "PUT",
        body: JSON.stringify({ preferred_genres: pendingGenres, preferred_authors: authors }),
      });
      setReader(updated);
      setAuthorPreference("");
      await loadRecommendations(updated.id);
      setSuccess("Your reading profile is updated. Your picks are ready.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update your preferences.");
    } finally {
      setSavingPreferences(false);
    }
  }

  const visiblePicks = recommendations.filter((pick) => !historyByBook.has(pick.book.id));

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#" onClick={() => setActiveView("discover")} aria-label="Folio home">
          <span className="brand-mark"><BookOpen size={19} /></span>
          <span>folio<span className="brand-period">.</span></span>
        </a>
        <nav className="main-nav" aria-label="Main navigation">
          <button className={activeView === "discover" ? "nav-link is-active" : "nav-link"} onClick={() => setActiveView("discover")}>Discover</button>
          <button className={activeView === "for-you" ? "nav-link is-active" : "nav-link"} onClick={() => setActiveView("for-you")}>For you</button>
          <button className={activeView === "shelf" ? "nav-link is-active" : "nav-link"} onClick={() => setActiveView("shelf")}>My shelf</button>
        </nav>
        <div className="reader-pill">
          <span className="reader-avatar"><UserRound size={15} /></span>
          <span>{reader?.display_name ?? "Your reading space"}</span>
          <ChevronDown size={14} />
        </div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow"><span className="live-dot" /> YOUR NEXT CHAPTER STARTS HERE</span>
          <h1>Good books find<br />their <em>people.</em></h1>
          <p>Discover stories that feel like they were picked just for you.</p>
          <button className="hero-cta" onClick={() => setActiveView("for-you")}>
            Find my next read <ArrowRight size={17} />
          </button>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="orb orb-one" />
          <div className="orb orb-two" />
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="hero-book">
            <span className="hero-book__tiny">A FOLIO PICK</span>
            <BookOpen size={28} strokeWidth={1.3} />
            <span className="hero-book__title">Somewhere,<br />a story waits.</span>
            <span className="hero-book__rule" />
            <span className="hero-book__author">CURATED FOR YOU</span>
          </div>
          <span className="sparkle sparkle-a">✳</span>
          <span className="sparkle sparkle-b">✳</span>
          <span className="float-note"><Sparkles size={14} /> 829 stories to explore</span>
        </div>
        <div className="hero-footnote"><span>01</span> A PERSONAL LIBRARY, IN PROGRESS <ArrowDownRight size={15} /></div>
      </section>

      <section className="discovery-shell">
        <div className="section-heading">
          <div>
            <span className="eyebrow eyebrow-dark">{activeView === "discover" ? "THE LIBRARY" : activeView === "for-you" ? "CURATED FOR YOUR TASTE" : "YOUR READING JOURNEY"}</span>
            <h2>{activeView === "discover" ? "Find a feeling." : activeView === "for-you" ? "A little more you." : "Your shelf, your story."}</h2>
          </div>
          <div className="book-count"><Library size={15} /> <span>{activeView === "shelf" ? history.length : books.length} {activeView === "shelf" ? "rated" : "books"}</span></div>
        </div>

        {error && <div className="notice notice-error" role="alert">{error}</div>}
        {success && <div className="notice notice-success" role="status"><Check size={16} /> {success}</div>}

        {activeView === "discover" && (
          <>
            <div className="search-panel">
              <label className="search-box">
                <Search size={19} />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a title, an author, a feeling…" aria-label="Search books" />
                {query && <button className="clear-search" onClick={() => setQuery("")} aria-label="Clear search">×</button>}
              </label>
              <label className="filter-select">
                <span>MOOD</span>
                <select value={genre} onChange={(event) => setGenre(event.target.value)} aria-label="Filter by estimated genre">
                  <option value="">All genres</option>
                  {facets.genres.map((value) => <option value={value} key={value}>{value}</option>)}
                </select>
                <ChevronDown size={15} />
              </label>
              <label className="filter-author">
                <span>AUTHOR</span>
                <input value={author} onChange={(event) => setAuthor(event.target.value)} placeholder="Any author" list="author-options" />
                <datalist id="author-options">{facets.authors.map((name) => <option value={name} key={name} />)}</datalist>
              </label>
            </div>
            <p className="filter-note"><Sparkles size={13} /> {GENRE_HINT}</p>
          </>
        )}

        {activeView === "for-you" && (
          <div className="preferences-panel">
            <div className="preferences-intro">
              <span className="preferences-icon"><WandSparkles size={20} /></span>
              <div><h3>Teach Folio your taste</h3><p>Choose a few starting points. Your ratings will make these picks smarter over time.</p></div>
            </div>
            <form onSubmit={savePreferences}>
              <span className="field-label">I&apos;m in the mood for</span>
              <div className="genre-options">
                {facets.genres.map((value) => (
                  <label className={pendingGenres.includes(value) ? "genre-choice is-picked" : "genre-choice"} key={value}>
                    <input
                      type="checkbox"
                      checked={pendingGenres.includes(value)}
                      onChange={() => setPendingGenres((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value])}
                    />
                    {pendingGenres.includes(value) && <Check size={13} />}{value}
                  </label>
                ))}
              </div>
              <div className="author-preference">
                <label htmlFor="author-preference">Or follow an author</label>
                <div className="author-input-row">
                  <input id="author-preference" value={authorPreference} onChange={(event) => setAuthorPreference(event.target.value)} placeholder="e.g. Ursula K. Le Guin" list="author-options" />
                  <button type="submit" className="save-button" disabled={savingPreferences}>{savingPreferences ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />} Save taste</button>
                </div>
                {reader?.preferred_authors.length ? <p className="saved-authors">Following: {reader.preferred_authors.join(" · ")}</p> : null}
              </div>
              {reader?.preferred_authors.length === 0 && !authorPreference.trim() && (
                <button type="submit" className="save-button save-button--standalone" disabled={savingPreferences}>{savingPreferences ? "Saving…" : "Save my preferences"} <ArrowRight size={16} /></button>
              )}
            </form>
          </div>
        )}

        {activeView === "shelf" ? (
          history.length ? (
            <div className="book-grid">
              {history.map((rating) => {
                const book = books.find((item) => item.id === rating.book_id) ?? recommendations.find((item) => item.book.id === rating.book_id)?.book;
                return book ? <BookCard key={rating.id} book={book} currentRating={rating.value} onRate={rateBook} saving={savingRating === book.id} /> : null;
              })}
            </div>
          ) : (
            <div className="empty-state"><Bookmark size={24} /><h3>Your shelf is still a blank page.</h3><p>Rate a book you have read and we&apos;ll start building your reading history.</p><button onClick={() => setActiveView("discover")}>Explore the library <ArrowRight size={15} /></button></div>
          )
        ) : activeView === "for-you" ? (
          <section className="recommendation-section">
            <div className="subsection-title"><div><span className="eyebrow eyebrow-dark">THE ALGORITHM, WITH A HEART</span><h3>Picked for your next chapter</h3></div><span className="hybrid-label"><Sparkles size={13} /> HYBRID PICKS</span></div>
            {loading ? <Loading /> : visiblePicks.length ? (
              <div className="book-grid">{visiblePicks.map((pick) => <BookCard key={pick.book.id} book={pick.book} recommendation={pick} currentRating={historyByBook.get(pick.book.id)} onRate={rateBook} saving={savingRating === pick.book.id} />)}</div>
            ) : <div className="empty-state"><Heart size={24} /><h3>Your next favorite is one rating away.</h3><p>Rate a couple of books to make your recommendations more personal.</p><button onClick={() => setActiveView("discover")}>Browse books <ArrowRight size={15} /></button></div>}
            <p className="model-note">Blends item similarity from collaborative filtering, metadata overlap, your ratings, and stated preferences. This catalog has no descriptions or verified genre metadata.</p>
          </section>
        ) : (
          <section className="catalog-section">
            <div className="subsection-title">
              <div><span className="eyebrow eyebrow-dark">A FEW PLACES TO BEGIN</span><h3>{query || genre || author ? "Your search results" : "Readers keep coming back to"}</h3></div>
              <button className="text-button" onClick={() => setActiveView("for-you")}>Your personal picks <ArrowRight size={15} /></button>
            </div>
            {loading ? <Loading /> : books.length ? (
              <div className="book-grid">{books.map((book) => <BookCard key={book.id} book={book} currentRating={historyByBook.get(book.id)} onRate={rateBook} saving={savingRating === book.id} />)}</div>
            ) : <div className="empty-state"><Compass size={24} /><h3>No matching stories yet.</h3><p>Try a different title, author, or genre.</p><button onClick={() => { setQuery(""); setGenre(""); setAuthor(""); }}>Clear filters <ArrowRight size={15} /></button></div>}
          </section>
        )}

        <footer className="footer">
          <a className="brand brand--footer" href="#"><span className="brand-mark"><BookOpen size={16} /></span>folio<span className="brand-period">.</span></a>
          <span>Made for the love of getting lost in a good book.</span>
          <span className="footer-meta">A PORTFOLIO PROJECT <span>·</span> <a href={`${API_URL.replace(/\/api\/v1$/, "")}/docs`} target="_blank" rel="noreferrer">API DOCS <ArrowRight size={11} /></a></span>
        </footer>
      </section>
    </main>
  );
}

function Loading() {
  return <div className="loading-state"><LoaderCircle className="spin" size={23} /><span>Finding your next favorite…</span></div>;
}
