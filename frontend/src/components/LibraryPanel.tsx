"use client"

import { useState, useEffect } from "react"
import { LibraryBook, LibrarySource } from "@/types"
import { libraryListBooks, libraryIngestBook, libraryDeleteBook, librarySearch } from "@/lib/api"

const CATEGORIES = [
  { value: "survival",     label: "Survival" },
  { value: "medical",      label: "Medical" },
  { value: "construction", label: "Construction" },
  { value: "farming",      label: "Farming" },
  { value: "education",    label: "Education" },
  { value: "reference",    label: "Reference" },
  { value: "general",      label: "General" },
]

const CATEGORY_COLOR: Record<string, string> = {
  survival:     "text-orange-400",
  medical:      "text-red-400",
  construction: "text-yellow-400",
  farming:      "text-green-400",
  education:    "text-blue-400",
  reference:    "text-purple-400",
  general:      "text-muted",
}

export default function LibraryPanel() {
  const [books, setBooks]           = useState<LibraryBook[]>([])
  const [loading, setLoading]       = useState(true)
  const [showAdd, setShowAdd]       = useState(false)
  const [ingesting, setIngesting]   = useState(false)
  const [ingestError, setIngestError] = useState("")

  const [filePath, setFilePath]   = useState("")
  const [title, setTitle]         = useState("")
  const [category, setCategory]   = useState("general")

  const [searchQuery, setSearchQuery]     = useState("")
  const [searchResults, setSearchResults] = useState<LibrarySource[]>([])
  const [searching, setSearching]         = useState(false)
  const [searchError, setSearchError]     = useState("")

  useEffect(() => { loadBooks() }, [])

  async function loadBooks() {
    setLoading(true)
    const data = await libraryListBooks()
    if (!data.error) setBooks(data.books)
    setLoading(false)
  }

  async function handleIngest() {
    if (!filePath.trim() || ingesting) return
    setIngesting(true)
    setIngestError("")
    const derivedTitle = title.trim() || filePath.split("/").pop()?.replace(/\.[^.]+$/, "") || "Untitled"
    const data = await libraryIngestBook(filePath.trim(), derivedTitle, category)
    if (data.error) {
      setIngestError(data.error)
    } else {
      setFilePath("")
      setTitle("")
      setCategory("general")
      setShowAdd(false)
      await loadBooks()
    }
    setIngesting(false)
  }

  async function handleDelete(bookId: string) {
    await libraryDeleteBook(bookId)
    setBooks((prev) => prev.filter((b) => b.book_id !== bookId))
    setSearchResults((prev) => prev.filter((r) => r.book_id !== bookId))
  }

  async function handleSearch() {
    if (!searchQuery.trim() || searching) return
    setSearching(true)
    setSearchError("")
    const data = await librarySearch(searchQuery, 8)
    if (data.error) setSearchError(data.error)
    else setSearchResults(data.results)
    setSearching(false)
  }

  function clearSearch() {
    setSearchQuery("")
    setSearchResults([])
    setSearchError("")
  }

  const grouped = books.reduce<Record<string, LibraryBook[]>>((acc, book) => {
    const cat = book.category || "general"
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(book)
    return acc
  }, {})

  return (
    <div className="flex flex-col h-full min-h-0">

      {/* Header */}
      <div className="flex items-center justify-between px-2 pb-2 mb-1 border-b border-muted/10">
        <span className="text-[10px] text-muted font-medium">
          {books.length} {books.length === 1 ? "book" : "books"} indexed
        </span>
        <button
          onClick={() => { setShowAdd(!showAdd); setIngestError("") }}
          className={`text-[10px] px-2.5 py-1 rounded-[10px] transition-all ${
            showAdd
              ? "neu-inset-sm text-accent"
              : "neu-extruded-sm text-accent hover:text-fg"
          }`}
        >
          {showAdd ? "Cancel" : "+ Add Book"}
        </button>
      </div>

      {/* Add book form */}
      {showAdd && (
        <div className="shrink-0 mb-2 p-3 rounded-[16px] neu-inset-sm space-y-2 animate-slide-down">
          <input
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleIngest()}
            placeholder="/path/to/book.pdf or .epub or .txt"
            className="w-full bg-transparent text-fg text-[10px] px-3 py-2 rounded-[10px] neu-inset-sm placeholder:text-muted/50 focus:outline-none"
          />
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (auto-detected from filename)"
            className="w-full bg-transparent text-fg text-[10px] px-3 py-2 rounded-[10px] neu-inset-sm placeholder:text-muted/50 focus:outline-none"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full bg-[#E0E5EC] text-fg text-[10px] px-3 py-2 rounded-[10px] neu-inset-sm focus:outline-none cursor-pointer"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
          {ingestError && (
            <p className="text-red-400 text-[10px] leading-relaxed">{ingestError}</p>
          )}
          <button
            onClick={handleIngest}
            disabled={ingesting || !filePath.trim()}
            className="w-full py-2 rounded-[10px] text-[10px] font-medium neu-extruded-sm text-accent hover:text-fg transition-all disabled:opacity-40"
          >
            {ingesting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-2.5 h-2.5 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
                Indexing…
              </span>
            ) : "Index Book"}
          </button>
        </div>
      )}

      {/* Search bar */}
      <div className="shrink-0 mb-2 flex gap-1.5">
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search library…"
          className="flex-1 bg-transparent text-fg text-[10px] px-3 py-2 rounded-[10px] neu-inset-sm placeholder:text-muted/50 focus:outline-none"
        />
        {searchResults.length > 0 || searchQuery ? (
          <button
            onClick={clearSearch}
            className="px-2.5 py-2 rounded-[10px] text-[10px] neu-extruded-sm text-muted hover:text-fg transition-all"
          >
            ✕
          </button>
        ) : null}
        <button
          onClick={handleSearch}
          disabled={searching || !searchQuery.trim()}
          className="px-3 py-2 rounded-[10px] text-[10px] neu-extruded-sm text-accent hover:text-fg transition-all disabled:opacity-40"
        >
          {searching
            ? <span className="w-2 h-2 border border-accent/30 border-t-accent rounded-full animate-spin block" />
            : "Go"
          }
        </button>
      </div>

      {/* Search results */}
      {searchError && (
        <p className="shrink-0 text-red-400 text-[10px] px-1 mb-2">{searchError}</p>
      )}
      {searchResults.length > 0 && (
        <div className="shrink-0 mb-3 space-y-1.5">
          <p className="text-[9px] font-display font-bold text-muted/70 uppercase tracking-widest px-1">
            {searchResults.length} results
          </p>
          {searchResults.map((r, i) => (
            <div key={i} className="p-2.5 rounded-[12px] neu-inset-sm space-y-1">
              <div className="flex items-center justify-between">
                <p className="text-[9px] font-medium text-accent truncate">{r.title}</p>
                <span className="text-[9px] text-muted shrink-0 ml-1">{Math.round(r.score * 100)}%</span>
              </div>
              <p className="text-[10px] text-fg/70 leading-relaxed line-clamp-3">{r.text}</p>
            </div>
          ))}
        </div>
      )}

      {/* Book list */}
      <div className="flex-1 overflow-auto space-y-3 pr-1 min-h-0">
        {loading && (
          <p className="text-muted text-[11px] p-2 animate-pulse">Loading library…</p>
        )}
        {!loading && books.length === 0 && (
          <div className="text-center py-6 px-2">
            <p className="text-muted text-[11px]">Library is empty.</p>
            <p className="text-muted/50 text-[10px] mt-1 leading-relaxed">
              Add PDFs, EPUBs, or text files.<br />
              Requires <span className="font-mono">nomic-embed-text</span> in Ollama.
            </p>
          </div>
        )}
        {Object.entries(grouped).map(([cat, catBooks]) => (
          <div key={cat}>
            <p className={`text-[9px] font-display font-bold uppercase tracking-widest px-1 mb-1.5 ${CATEGORY_COLOR[cat] ?? "text-muted"}`}>
              {cat} · {catBooks.length}
            </p>
            <div className="space-y-0.5">
              {catBooks.map((book) => (
                <div
                  key={book.book_id}
                  className="flex items-start gap-2 px-2 py-2 rounded-[12px] hover:neu-inset-sm transition-all group cursor-default"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-medium text-fg truncate">{book.title}</p>
                    <p className="text-[9px] text-muted">
                      {book.chunk_count} chunks · {book.added_at.slice(0, 10)}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(book.book_id)}
                    className="opacity-0 group-hover:opacity-100 text-[11px] text-muted hover:text-red-400 transition-all shrink-0 mt-0.5 px-1"
                    title="Remove book"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
