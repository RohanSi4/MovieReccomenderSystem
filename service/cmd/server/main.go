package main

import (
    "encoding/csv"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "math"
    "net/http"
    "os"
    "path/filepath"
    "sort"
    "strconv"
    "strings"
    "time"
)

type Movie struct {
    MovieID        int
    Title          string
    RatingMean     float64
    RatingCount    int
    TMDBVoteAvg    float64
    TMDBPopularity float64
    TMDBPosterPath string
    TMDBOverview   string
    TMDBRelease    string
}

type UserFeatures struct {
    UserID      int
    RatingMean  float64
    RatingCount int
}

type App struct {
    Movies       []Movie
    MoviesByID   map[int]Movie
    UsersByID    map[int]UserFeatures
    DataDir      string
    PosterBase   string
    ScoreWeights ScoreWeights
}

type ScoreWeights struct {
    VoteAvg   float64
    Pop       float64
    CountLog  float64
    UserBias  float64
    MeanBias  float64
}

type RankRequest struct {
    UserID int `json:"user_id"`
    K      int `json:"k"`
}

type RankResult struct {
    MovieID   int      `json:"movie_id"`
    Score     float64  `json:"score"`
    Title     string   `json:"title"`
    PosterURL string   `json:"poster_url"`
    Reasons   []string `json:"reasons,omitempty"`
}

type RankResponse struct {
    UserID    int          `json:"user_id"`
    Results   []RankResult `json:"results"`
    LatencyMS int64        `json:"latency_ms"`
}

func main() {
    dataDir := getEnv("MOVIE_DATA_DIR", "service/data")
    app := &App{
        DataDir:    dataDir,
        PosterBase: "https://image.tmdb.org/t/p/w342",
        ScoreWeights: ScoreWeights{
            VoteAvg:  0.15,
            Pop:      0.02,
            CountLog: 0.5,
            UserBias: 1.0,
            MeanBias: 1.0,
        },
    }

    if err := app.LoadData(); err != nil {
        log.Printf("Data load warning: %v", err)
    }

    mux := http.NewServeMux()
    mux.HandleFunc("/health", app.handleHealth)
    mux.HandleFunc("/rank", app.handleRank)
    mux.HandleFunc("/movie/", app.handleMovie)

    addr := getEnv("PORT", "8080")
    if !strings.HasPrefix(addr, ":") {
        addr = ":" + addr
    }

    log.Printf("Starting server on %s", addr)
    if err := http.ListenAndServe(addr, mux); err != nil {
        log.Fatal(err)
    }
}

func (a *App) LoadData() error {
    moviesPath := filepath.Join(a.DataDir, "movie_features.csv")
    usersPath := filepath.Join(a.DataDir, "user_features.csv")

    movies, err := loadMoviesCSV(moviesPath)
    if err != nil {
        return err
    }
    users, err := loadUsersCSV(usersPath)
    if err != nil {
        return err
    }

    a.Movies = movies
    a.MoviesByID = make(map[int]Movie, len(movies))
    for _, m := range movies {
        a.MoviesByID[m.MovieID] = m
    }

    a.UsersByID = make(map[int]UserFeatures, len(users))
    for _, u := range users {
        a.UsersByID[u.UserID] = u
    }

    log.Printf("Loaded %d movies, %d users", len(movies), len(users))
    return nil
}

func (a *App) handleHealth(w http.ResponseWriter, r *http.Request) {
    writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (a *App) handleRank(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    if r.Method != http.MethodPost {
        writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "POST required"})
        return
    }

    var req RankRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
        return
    }
    if req.K <= 0 {
        req.K = 25
    }

    user, ok := a.UsersByID[req.UserID]
    var userPtr *UserFeatures
    if ok {
        userPtr = &user
    }

    results := a.rankMovies(userPtr, req.K)
    latency := time.Since(start).Milliseconds()

    writeJSON(w, http.StatusOK, RankResponse{
        UserID:    req.UserID,
        Results:   results,
        LatencyMS: latency,
    })
}

func (a *App) handleMovie(w http.ResponseWriter, r *http.Request) {
    parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/movie/"), "/")
    if len(parts) == 0 || parts[0] == "" {
        writeJSON(w, http.StatusBadRequest, map[string]string{"error": "movie id required"})
        return
    }
    id, err := strconv.Atoi(parts[0])
    if err != nil {
        writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid movie id"})
        return
    }

    movie, ok := a.MoviesByID[id]
    if !ok {
        writeJSON(w, http.StatusNotFound, map[string]string{"error": "not found"})
        return
    }
    writeJSON(w, http.StatusOK, movie)
}

func (a *App) rankMovies(user *UserFeatures, k int) []RankResult {
    results := make([]RankResult, 0, k)

    type scored struct {
        Movie Movie
        Score float64
    }
    scoredMovies := make([]scored, 0, len(a.Movies))
    for _, m := range a.Movies {
        scoredMovies = append(scoredMovies, scored{Movie: m, Score: a.scoreMovie(m, user)})
    }

    sort.Slice(scoredMovies, func(i, j int) bool {
        return scoredMovies[i].Score > scoredMovies[j].Score
    })

    if k > len(scoredMovies) {
        k = len(scoredMovies)
    }
    for i := 0; i < k; i++ {
        m := scoredMovies[i].Movie
        results = append(results, RankResult{
            MovieID:   m.MovieID,
            Score:     scoredMovies[i].Score,
            Title:     m.Title,
            PosterURL: joinPosterURL(a.PosterBase, m.TMDBPosterPath),
            Reasons:   buildReasons(m, user),
        })
    }

    return results
}

func (a *App) scoreMovie(m Movie, user *UserFeatures) float64 {
    score := 0.0
    score += m.RatingMean
    score += a.ScoreWeights.VoteAvg * m.TMDBVoteAvg
    score += a.ScoreWeights.Pop * m.TMDBPopularity
    score += a.ScoreWeights.CountLog * math.Log1p(float64(m.RatingCount))

    if user != nil {
        score += a.ScoreWeights.UserBias * user.RatingMean
        score -= a.ScoreWeights.MeanBias * math.Abs(m.RatingMean-user.RatingMean)
    }
    return score
}

func buildReasons(m Movie, user *UserFeatures) []string {
    reasons := []string{}
    if m.TMDBVoteAvg >= 7.5 {
        reasons = append(reasons, "high_vote_avg")
    }
    if m.RatingCount >= 1000 {
        reasons = append(reasons, "popular_in_movielens")
    }
    if user != nil && math.Abs(m.RatingMean-user.RatingMean) <= 0.5 {
        reasons = append(reasons, "matches_user_taste")
    }
    return reasons
}

func loadMoviesCSV(path string) ([]Movie, error) {
    file, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer file.Close()

    reader := csv.NewReader(file)
    reader.FieldsPerRecord = -1

    header, err := reader.Read()
    if err != nil {
        return nil, err
    }
    idx := headerIndex(header)

    required := []string{"movieId", "title", "rating_mean", "rating_count"}
    for _, col := range required {
        if _, ok := idx[col]; !ok {
            return nil, fmt.Errorf("missing column %s in %s", col, path)
        }
    }

    var movies []Movie
    for {
        row, err := reader.Read()
        if err == io.EOF {
            break
        }
        if err != nil {
            if err == csv.ErrFieldCount {
                continue
            }
            return nil, err
        }

        movieID := parseInt(row, idx, "movieId")
        title := parseString(row, idx, "title")
        ratingMean := parseFloat(row, idx, "rating_mean")
        ratingCount := parseInt(row, idx, "rating_count")

        movies = append(movies, Movie{
            MovieID:        movieID,
            Title:          title,
            RatingMean:     ratingMean,
            RatingCount:    ratingCount,
            TMDBVoteAvg:    parseFloat(row, idx, "tmdb_vote_avg"),
            TMDBPopularity: parseFloat(row, idx, "tmdb_popularity"),
            TMDBPosterPath: parseString(row, idx, "tmdb_poster_path"),
            TMDBOverview:   parseString(row, idx, "tmdb_overview"),
            TMDBRelease:    parseString(row, idx, "tmdb_release_date"),
        })
    }

    return movies, nil
}

func loadUsersCSV(path string) ([]UserFeatures, error) {
    file, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    defer file.Close()

    reader := csv.NewReader(file)
    reader.FieldsPerRecord = -1

    header, err := reader.Read()
    if err != nil {
        return nil, err
    }
    idx := headerIndex(header)

    required := []string{"userId", "rating_mean", "rating_count"}
    for _, col := range required {
        if _, ok := idx[col]; !ok {
            return nil, fmt.Errorf("missing column %s in %s", col, path)
        }
    }

    var users []UserFeatures
    for {
        row, err := reader.Read()
        if err == io.EOF {
            break
        }
        if err != nil {
            if err == csv.ErrFieldCount {
                continue
            }
            return nil, err
        }

        users = append(users, UserFeatures{
            UserID:      parseInt(row, idx, "userId"),
            RatingMean:  parseFloat(row, idx, "rating_mean"),
            RatingCount: parseInt(row, idx, "rating_count"),
        })
    }

    return users, nil
}

func headerIndex(header []string) map[string]int {
    idx := make(map[string]int, len(header))
    for i, col := range header {
        idx[strings.TrimSpace(col)] = i
    }
    return idx
}

func parseString(row []string, idx map[string]int, col string) string {
    i, ok := idx[col]
    if !ok || i >= len(row) {
        return ""
    }
    return row[i]
}

func parseInt(row []string, idx map[string]int, col string) int {
    i, ok := idx[col]
    if !ok || i >= len(row) {
        return 0
    }
    val := strings.TrimSpace(row[i])
    if val == "" {
        return 0
    }
    parsed, err := strconv.Atoi(val)
    if err != nil {
        return 0
    }
    return parsed
}

func parseFloat(row []string, idx map[string]int, col string) float64 {
    i, ok := idx[col]
    if !ok || i >= len(row) {
        return 0
    }
    val := strings.TrimSpace(row[i])
    if val == "" {
        return 0
    }
    parsed, err := strconv.ParseFloat(val, 64)
    if err != nil {
        return 0
    }
    return parsed
}

func joinPosterURL(base, path string) string {
    if path == "" {
        return ""
    }
    return base + path
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    if err := json.NewEncoder(w).Encode(payload); err != nil {
        log.Printf("json encode error: %v", err)
    }
}

func getEnv(key, fallback string) string {
    if v := os.Getenv(key); v != "" {
        return v
    }
    return fallback
}
