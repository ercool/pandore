import guessit
import requests
import re
import os
from datetime import date
from imdb import IMDb
from series.models import (Series, Season, Episode, Genre, SeriesContributors,
                           EpisodeContributors, SeriesDirectory,
                           SeasonDirectory, EpisodeDirectory)
from people.models import Person
from movies.utils import get_size


class SeriesDirectoryProcessor(object):
    __reg_dir_s = r'(.*/)?(.+)'
    __reg_bing_s = r'www.imdb.com/title/tt(?P<id>\d+)/'
    __reg_episode_s = r'(S[0-9]{1,2}E[0-9]{1,3}|\.E[0-9]{1,2}\.|[0-9]{1,2}x[0-9]{1,3})'
    title = quality = year = id_imdb = None

    def __init__(self):
        self.__reg_dir = re.compile(self.__reg_dir_s)
        self.__reg_bing = re.compile(self.__reg_bing_s)
        self.__reg_episode = re.compile(self.__reg_episode_s)
        self.reset_infos()
        self.series_processor = SeriesProcessor()
        self.episode_dir_processor = EpisodeProcessor()
        self.ia = IMDb()
        self.series_on_imdb = None

    def reset_infos(self):
        self.title = self.quality = self.year = self.id_imdb = None
        self.directory = None
        self.processed = False
        self.series_on_imdb = None

    def process(self, directory):
        self.reset_infos()
        self.directory = os.path.abspath(directory)

        dir = self.__reg_dir.match(self.directory).group(2) + '/'
        guess = guessit.guess_movie_info(dir)
        if not 'title' in guess:
            print 'Error while processing ' + self.directory
            return False

        filter = SeriesDirectory.objects.filter(location=self.directory)
        if filter.exists():
            self.series = filter[0]
        else:
            # Search series on bing
            self.year = str(guess['year']) if 'year' in guess else ''
            search_string = 'site:imdb.com %s %s' % (guess['title'], year)
            r = requests.get(
                    'http://www.bing.com/search', params={'q': search_string})
            match = self.__reg_bing.search(r.content)
            if not match:
                print r.url
                print "Bing wasn't able to find this series, skipping"
                return False
            self.id_imdb = match.group('id')
            self.title = guess['title']
            self.save()

        # Search episodes in series directory
        dirs = [self.directory]
        for d in dirs:
            if not self.__reg_episode.search(d):
                for d2 in [d+dir+'/' for dir in os.listdir(d)
                           if os.path.isdir(d+dir)]:
                    dirs.append(d2)
            else:
                if not self.series_on_imdb:
                    self.series_on_imdb = self.ia.get_movie(self.series.id_imdb)
                    self.ia.update(self.series_on_imdb, 'episodes')
                self.episode_dir_processor.process(d, self.series,
                        self.series_on_imdb['episodes'])

        return True

    def save(self):
        self.series = self.series_processor.process(self.id_imdb)
        SeriesDirectory.objects.create(
            series=self.series, location=self.directory)


class EpisodeDirectoryProcessor()
    title = quality = year = id_imdb = None

    def __init__(self):
        self.reset_infos()

    def reset_infos(self):
        self.title = self.quality = self.year = self.id_imdb = None
        self.directory = None
        self.processed = False
        self.series_on_imdb = None
        self.episode_processor = EpisodeProcessor()

    def process(self, directory, series_bdd, series_imdb):
        self.reset_infos()
        self.path = os.path.abspath(directory)
        self.filename = os.path.basename(self.path)
        self.season_directory = os.path.dirname(self.path)

        guess = guessit.guess_movie_info(self.filename)
        if 'season' in guess.keys and 'episodeNumber' in guess.keys:
            self.season_nb = guess['season']
            self.episode_nb = guess.['episodeNumber']
        else:
            print self.path
            print 'Error: Episode wrongly named'
            return
        :
        self.quality = guess['screenSize'] if 'screenSize' in guess else 'SD'

        filter = Season.objects.filter(series=series_bdd,
                                       season_number=self.season_nb)
        if filter.exists():
            self.season = filter[0]
        else:
            self.season = Season.objects.create(series=series_bdd,
                                                season_number=self.season_nb,
                                                number_of_episodes=0)
            
        filter = SeasonDirectory.objects.filter(season=self.season,
                                                location=self.season_directory,
                                                quality=self.quality)
        if filter.exists():
            self.season_dir = filter[0]
        else:
            self.season_dir = SeasonDirectory.objects.create(
                    season=self.season, location=self.season_directory,
                    quality=self.quality)

        filter = Episode.objects.filter(season=self.season,
                                        episode_number=self.episode_nb)
        if filter.exists():
            self.episode = filter[0]
        else:
            if self.season_nb in series_imdb.keys() and
                    self.episode_nb in series_imdb[self.season_nb].keys():
                self.episode = self.episode_processor.process(
                        series_imdb[self.season_nb][self.episode_nb])

        #TODO: Create Episode Directory
        #filter = EpisodeDirectory.objects.filter(


class SeriesProcessor(object):
    __reg_title_vf_s = r'(.+)::.*France'
    __reg_title_int_s = r'(.+)::.*International'
    title = title_fr = year = runtime = id_imdb = poster = rating = None
    votes = plot = language = genres = persons = None
    imdb_infos = None

    def __init__(self):
        self.__reg_title_vf = re.compile(self.__reg_title_vf_s)
        self.__reg_title_int = re.compile(self.__reg_title_int_s)
        self.ia = IMDb()

    def reset_infos(self):
        self.title = self.title_fr = self.id_imdb = self.poster = ''
        self.plot = self.language = ''
        self._begin_year = self._end_year = self.runtime = None
        self.rating = self.votes = None
        self.genres = []
        self.persons = {'cast': [], 'director': [], 'writer': []}
        self.imdb_infos = None

    def get_title_fr(self):
        if 'akas' in self.imdb_infos.keys():
            for title in self.imdb_infos['akas']:
                match = self.__reg_title_vf.search(title)
                if match:
                    return match.group(1)
        return None

    def get_title_int(self):
        if 'akas' in self.imdb_infos.keys():
            for title in self.imdb_infos['akas']:
                match = self.__reg_title_int.search(title)
                if match:
                    return match.group(1)
        return None

    def process(self, id_imdb):
        self.reset_infos()
        self.id_imdb = id_imdb
        existing = Series.objects.filter(id_imdb=id_imdb).exists()
        if existing:
            print "Series already in the database"
            return Series.objects.get(id_imdb=id_imdb)
        self.imdb_infos = self.ia.get_movie(id_imdb)
        if not len(self.imdb_infos):
            print 'Unvalid imdb id : %s, aborting...' % id_imdb
            return False
        self.title = self.imdb_infos['title']
        # Making alias
        self.alias = ''
        for w in self.title.split():
            if w:
                self.alias += w[0]
        if len(self.alias) < 2:
            self.alias = ""
        if 'series years' in self.imdb_infos.keys():
            y = self.imdb_infos['series years'].split("-")
            self.begin_year = int(y[0])
            # Doesn't work with mini-series
            self.end_year = int(y[1]) if y[1] else date.today().year
        else:
            self.begin_year = self.end_year = self.imdb_infos['year']
        self.title_fr = self.get_title_fr()
        if self.title_fr:
            self.title_fr = self.title_fr.encode('utf-8')
        else:
            self.title_fr = self.title
        self.title_int = self.get_title_int()
        if self.title_int:
            self.title_int = self.title_int.encode('utf-8')
        else:
            self.title_int = self.title
        if 'cover url' in self.imdb_infos.keys():
            self.poster = self.imdb_infos['cover url']
        if 'rating' in self.imdb_infos.keys():
            self.rating = self.imdb_infos['rating']
        if 'votes' in self.imdb_infos.keys():
            self.votes = self.imdb_infos['votes']
        if 'plot outline' in self.imdb_infos.keys():
            self.plot = self.imdb_infos['plot outline']
        if 'language codes' in self.imdb_infos.keys():
            self.language = self.imdb_infos['language codes'][0]
        if 'genres' in self.imdb_infos.keys():
            self.genres = self.imdb_infos['genres']
        if 'cast' in self.imdb_infos.keys():
            self.persons['cast'] = self.imdb_infos['cast']
        if 'director' in self.imdb_infos.keys():
            self.persons['director'] = self.imdb_infos['director']
        if 'writer' in self.imdb_infos.keys():
            self.persons['writer'] = self.imdb_infos['writer']
        #TODO take care of encoding where it needs to.
        m = self.save()
        return m

    def save(self):
        m = Series.objects.create(
                title=self.title, title_fr=self.title_fr,
                title_int=self.title_int, begin_year=self.begin_year,
                end_year=self.end_year, id_imdb=self.id_imdb,
                poster=self.poster, rating=self.rating,
                votes=self.votes, plot=self.plot,
                language=self.language, alias=self.alias,
                number_of_episodes=0, number_of_seasons=0)
        m.save()
        for idx, actor in enumerate(self.persons['cast']):
            p = Person.add(actor)
            SeriesContributors.objects.create(
                    person=p, series=m, function='A', rank=idx)
        for idx, director in enumerate(self.persons['director']):
            p = Person.add(director)
            SeriesContributors.objects.create(
                    person=p, series=m, function='D', rank=idx)
        for idx, writer in enumerate(self.persons['writer']):
            p = Person.add(writer)
            p.save()
            SeriesContributors.objects.create(
                    person=p, series=m, function='W', rank=idx)
        for genre in self.genres:
            print genre
            g = Genre.add(genre)
            m.genres.add(g)
        return m

#TODO: Class to add Episode