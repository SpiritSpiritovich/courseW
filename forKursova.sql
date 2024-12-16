USE forKursova;
Create table Games (
    GameID int primary key,
    Title nvarchar(100),
    Genre nvarchar(50),
    ReleaseYear int,
    Rating float,
    Price DECIMAL (10, 2)
);

CREATE TABLE Genres (
    GenreID INT PRIMARY KEY,
    GenreName NVARCHAR(50)
);

CREATE TABLE UserRatings (
    RatingID INT PRIMARY KEY,
    UserID INT,
    GameID INT,
    Rating FLOAT,
    Review NVARCHAR(500)
);

SELECT * FROM Games;

