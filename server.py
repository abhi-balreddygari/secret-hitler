import os
import random
import time
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room

#The following class manages Rooms. It stores various variables to do with 
#voting, player roles and full a room is, and the state of cards. 
class Room:
    def __init__(self, size):
        #This variable counts how many players are ready in the lobby 
        # (i.e how many players are named.)
        self.ready = 0
        
        #These variables store the size of the room and whether 
        #it is full.
        self.size = int(size)
        self.filled = False
        
        #These variables hold the players, the name of the president
        #and the name of the chancellor
        self.players = []
        self.president= ""
        self.chancellor = ""
        self.presIndex = 0

        #These variables stores information about voting. 
        self.voteYes = 0
        self.voteNo = 0
        self.votingArray = []
        self.voted = True
        self.ineligible = []
        self.failedVotes = 0

        #These variables store information about the state
        #of the deck, and whether cards have been shown
        #to particular players
        self.currentCards = []
        self.sentCards = False
        self.deck = ["F"]*11 + ["L"]*6
        self.discards = []

        #This variable stores information about the state of the board
        self.board = {"F":0,"L":0}
        
        #These variables track whether things have happened
        self.investigation = False
        self.specialPresidency = False
    
    #This method allows a player to be added into a list, and modifies
    #the size and filled parameters accordingly.
    def addPlayer(self, playerObject):
        self.players.append(playerObject)
        if len(self.players) == self.size:
            self.filled = True

    def removePlayer(self, name):
        self.players.remove(name)
    
    #This method sets the first President at index 0.
    def getPresident(self):
        self.president = self.players[self.presIndex].name
        return self.president

    #This method finds the next player in the player list and
    #sets them as president.
    def nextPresident(self):
        self.presIndex = (self.presIndex + 1) % self.size
        self.president = self.players[self.presIndex].name
        return self.president
    
    #This method gives the list of candidates for Chancellor, excluding
    #the current president, and immediately former chancellors
    #and presidents.
    def getChancellorCandidates(self):
        playerList = []
        self.ineligible.append(self.president)
        for player in self.players:
            playerList.append(player.name)
        finalList = [user for user in playerList if user not in self.ineligible]
        return finalList

    def getPlayers(self):
        L = []
        for player in self.players:
            if player.dead == False and player.name != self.president:
                L.append(player.name)
        print(L)
        return L
      
class Player:
    def __init__(self, ID):
        self.ID = ID
        self.name = None
        self.role = None
        self.dead = False
    def setName(self, name):
        self.name = name
        
        
DATA = {}       
#The DATA variable acts as the database for the entire application.
#The expected format for the database is as follows:
#{'<room>':Room class}

USERIds = {}
#The USERIds variable is used to generate unique <userId>'s with efficiency.

app = Flask(__name__)
#Initiate flask application

socketio = SocketIO(app)
#Initiate SocketIo application



#The follwing three functions are for handling basic routing to display,
#the three main pages of the application home, lobby and game.
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/lobby")
def lobby():
    return render_template("lobby.html")


@app.route("/game")
def game():
     return render_template("game.html")



#This function handles the process of creating a room, it takes as input
#from a POST call, the user declared room size and returns the room code
#It then adds the room code into the DATA variable and initiates it with
#ready: 0 and size: <size>
@app.route("/api/createroom", methods = ["POST"])
def createRoom():
    roomSize = request.data.decode("UTF-8")
    roomCode = ""
    for i in range(4):
        roomCode += chr(random.randint(65,90))
    if DATA.get(roomCode,0) == 0:
        x = Room(roomSize)
        DATA[roomCode] = x
        return jsonify({"roomCode":roomCode})
    createRoom()


#This function handles the process of joining a room, it takes as input 
#from a POST call, the user declared room code and returns the following
#error codes: 0 -> success, 1 -> room does not exist, 2 -> room is full
@app.route("/api/joinroom", methods = ["POST"])
def joinRoom(): 
    code = request.data.decode("UTF-8")
    if DATA.get(code,0) == 0: 
        return jsonify({"errorCode":"1"})
    if DATA[code].filled == True:
        return jsonify({"errorCode":"2"})
    return jsonify({"errorCode":"0"})


#This function handles the process of randomly and uniquely generating
#unique user userIds in response to a GET request which is sent the first
#time a user visits the homepage.
@app.route("/api/generateuserid", methods = ["GET"])
def generate():
    userID = ""
    for i in range(10):
        userID += str(random.randint(0,9))
    if USERIds.get(userID,0) == 0:
        return jsonify({"userID":userID})
    generate()


#This function serves to update the lobby page on refresh or onload and
#return a list of currently ready players in the current room specified 
#on the socket emit.
@socketio.on("onLoadLobby")
def handleOnLoadLobby (room): 
    userArray = []
    for player in DATA[room].players:
            username = player.name
            if username != None:
                userArray.append(username)
    emit("onLoadLobbyResponse",{"userArray":userArray})


#This function serves to keep a record of players who have entered the 
#particular lobby by adding a record to the database specified by the
#room and userId which are passed as arguments on socket emit. The response
#0 is sent to indicate a succesful record of a new user.
@socketio.on("newUser")
def handleNewUser(userId,room):
    join_room(room)
    idList = []
    for player in DATA[room].players:
        idList.append(player.ID)
    if userId not in idList:
        x = Player(userId)
        DATA[room].addPlayer(x)
        emit("newUserResponse","0", room=room)


#This function allows a user in a particulular room set a name once and 
#only once, without allowing duplicates with other users in the room. The
#userId, username and room are passed as arguments during the socket emit.
#The function returns the following errorCodes: 0 -> success, 1 -> user
#name already in use.
@socketio.on("addName")
def handleAddName(userId,username,room):
    for player in DATA[room].players:
        if username == player.name:
            emit("addNameSelf",{"errorCode":"1"})
            return
    DATA[room].ready = DATA[room].ready +1 
    for player in DATA[room].players:
        if userId == player.ID:
            player.setName(username)
    emit("addNameSelf",{"errorCode":"0","name":username})
    emit("addNameRoom", username, room=room)

    #This block of code is responsible for signalling that the final user 
    #has selected their name and thus the game is ready to begin. It also
    #handles the process of allocating the roles of Fascist (F), Hitler (H)
    #and liberal in a random process according to the corect frequencies. The
    #cards are also shuffled.
    size = DATA[room].size
    if DATA[room].ready == size:
        if size in [5,6]:
            F = 1
        if size in [7,8]:
            F = 2
        if size in [9,10]:
            F = 3
    
        A = random.sample(range(1,size),F+1)
        H = random.choice(A)
        i = 0
        for player in DATA[room].players:
            i += 1
            if i in A: 
                player.role = "Fascist"
            else: 
                player.role = "Liberal"
            if i == H: 
                player.role = "Hitler"
        
        random.shuffle(DATA[room].deck)
        emit("begin","0",room=room)
        

#This function is used to pass the various roles of the players
#on to the client side once the game room is reached.
@socketio.on("getRole")
def handleRole(room, userId):
    for player in DATA[room].players:
        if player.ID == userId:
            playerRole = player.role
            emit("getRoleResponse", player.role)
    A = []
    for player in DATA[room].players:
        A.append({"name":player.name, "role": player.role})
    emit("getPlayersResponse", {"array":A, "role":playerRole})
        
#This function runs the game, ensuring that when players refresh and return 
#are given the right game information for a certain point in time
@socketio.on("onLoadGame")
def gamestart(room, name):
    join_room(room)
    #This part of the function deals with if the president joins or 
    #rejoins the game.
    if DATA[room].president == name:
        print(DATA[room].investigation)
        print(DATA[room].chancellor)
        print(DATA[room].sentCards)
        if DATA[room].investigation == True:
            emit("investigationSelection",{"president":DATA[room].president, 
                    "players":DATA[room].getPlayers(), "board":DATA[room].board})
            return
        #This part of the code gives the president the chancellor
        #candidates if it has not already been picked.
        elif DATA[room].chancellor == "":
            presidentData = {"president": DATA[room].president, \
                "chancellorCandidates": DATA[room].getChancellorCandidates(), \
                    "board":DATA[room].board}
            emit("president", presidentData)
        #This part of the code gives the president their voting 
        #options if they have not yet voted for anyone.
        elif DATA[room].voted == False:
            for item in DATA[room].votingArray:
                if item[0] == name:
                    return
            emit("voting", DATA[room].chancellor)
        #This part of the code checks if the president has been
        #given their voting cards and displays them if they 
        #haven't. This is tracked by the .sentCards variable
        elif DATA[room].sentCards == False:
            emit("sendCardsPresident", DATA[room].currentCards)
            return
    #This part of the function deals with if the chancellor joins or 
    #rejoins the game.    
    elif DATA[room].chancellor == name:
        #This part of the code gives the chancellor their voting 
        #options if they have not yet voted for anyone.
        if DATA[room].voted == False:
            for item in DATA[room].votingArray:
                if item[0] == name:
                    return
            emit("voting", DATA[room].chancellor)
        #This part of the code checks if the president has passed on
        # their cards and displays the remaining to the chancellor 
        # if the chancellor has not sent
        # them on. This is tracked by the .sentCards variable
        elif DATA[room].sentCards == True:
            cards = DATA[room].currentCards
            emit("sendCardsChancellor",{"cards":cards, \
                "chancellor":DATA[room].chancellor}, room=room)
            return
    else:
        #This part of the code picks a president if none has been picked 
        #and initializes the president
        if DATA[room].president == "":
            DATA[room].getPresident()
            presidentData = {"president": DATA[room].president, \
                "chancellorCandidates": DATA[room].getChancellorCandidates(), \
                "board":DATA[room].board}
            emit("president", presidentData)
        #This part of the code checks if a player has voted and sends
        #voting information if they have not. 
        elif DATA[room].voted == False:
            for item in DATA[room].votingArray:
                if item[0] == name:
                    return
            emit("voting", DATA[room].chancellor)

#This function stores the chancellor selection received from 
#the president and initializes voting
@socketio.on("chancellorSelection")
def getSelection(chancellor, room):
    DATA[room].chancellor = chancellor
    DATA[room].voted = False
    emit("voting", chancellor, room=room)

#This function handles voting. It adds the yes and no votes
#as they come from the clients and when everyone has voted
#it handles the consequences of a yes and no votes
@socketio.on("vote")
def handleVote(vote,room,name):
    #votingArray stores every players' votes
    DATA[room].votingArray.append([name,vote])
    #player votes are tallied
    if vote == "Yes":
        DATA[room].voteYes += 1
    if vote == "No":
        DATA[room].voteNo += 1
    #once everyone has voted some variables are set (and ineligible
    #chancellors for the next round are initializied.)
    if DATA[room].voteNo + DATA[room].voteYes == DATA[room].size:
        DATA[room].voted = True
        majority = "No"
        if DATA[room].specialPresidency == False:
            DATA[room].ineligible = []
            DATA[room].ineligible.append(DATA[room].president)
        #If the majority vote yes, the current chancellor is added
        #to ineligible candidates, and the result of the vote is 
        #sent to all the clients.
        if DATA[room].voteYes > DATA[room].voteNo:
            DATA[room].failedVotes = 0
            majority = "Yes"
            if DATA[room].specialPresidency == False:
                DATA[room].ineligible.append(DATA[room].chancellor)
            
            DATA[room].specialPresidency = False

            emit("voteResult", {"majority": majority,
                "votingArray": DATA[room].votingArray, 
                "president": DATA[room].president, 
                "chancellor": DATA[room].chancellor}, room=room)
        #If the majority votes no a new president is selected and 
        #the chancellor choice is reset. 
        else:
            DATA[room].failedVotes += 1
            skipMessage = ""
            if DATA[room].failedVotes == 3:
                firstCard = DATA[room].deck.pop(0)
                DATA[room].board[firstCard] += 1
                skipMessage = "Three failed votes - a card was placed on board"
                DATA[room].failedVotes = 0 
            emit("voteResult", {"majority": majority, \
                "votingArray": DATA[room].votingArray, \
                    "president": DATA[room].president, \
                        "chancellor": DATA[room].chancellor, \
                            "message": skipMessage}, room=room)
            DATA[room].chancellor = ""
            DATA[room].nextPresident()
        #After the vote all the voting variables are reset. The 
        #result is sent to all clients
        DATA[room].voteNo = 0
        DATA[room].voteYes = 0
        DATA[room].votingArray = []

#The cards are sent to the president
@socketio.on("getCardsPresident")
def handleGetCards(room):
    #The deck is shuffled if not enough cards remain
    if len(DATA[room].deck) < 3:
        DATA[room].deck = DATA[room].deck + DATA[room].discard
        random.shuffle(DATA[room].deck)
    #3 cards are drawn from the top of the deck.
    cards = []
    for i in range(3):
        cards.append(DATA[room].deck.pop(0))    
    #The list of cards are stores in case stored 
    #in case the president leaves and rejoins.
    DATA[room].currentCards = cards
    emit("sendCardsPresident",cards)

#This functions recieves the discarded card information
#from the client and sends the remaining cards to the 
#chancellor
@socketio.on("discardPresident")
def handleDiscard(discard,cards,room):
    cards.remove(discard)
    DATA[room].discards.append(discard)
    DATA[room].currentCards = cards
    DATA[room].sentCards = True
    emit("sendCardsChancellor",{"cards":cards, \
        "chancellor":DATA[room].chancellor},room=room)

#Where the vote fails, this function is activated and sends the 
#selecting chancellor data to the president
@socketio.on("handler")
def responder(code, room):
    if code == "2":
        DATA[room].nextPresident()
    presidentData = {"president": DATA[room].president, \
            "chancellorCandidates": DATA[room].getChancellorCandidates(),\
                "board":DATA[room].board}
    emit("president", presidentData, room=room)   

#This function updates the board once the chancellor has picked their
#card.
@socketio.on("updateBoard")
def handleUpdateBoard(card,cards,room):
    #Adding the discarded card into the discard pile and also adding the
    #selected card onto the board
    discard = cards.remove(card)
    DATA[room].discards.append(discard)
    DATA[room].board[card] += 1
    #Getting the chancellor selections which may include the next president
    #but not the previous president or chancellor
    DATA[room].sentCards = False
    DATA[room].currentCards = []
    DATA[room].chancellor = ""
    if DATA[room].board["F"] == 6:
        emit("gameOver","F",room=room)
    if DATA[room].board["L"] == 6:
        emit("gameOver","L",room=room)
    if card == "F":
        if (DATA[room].board["F"] == 1 and DATA[room].size in [9,10]) \
            or (DATA[room].board["F"] == 2 and DATA[room].size in [7,8,9,10]):
                DATA[room].investigation = True
                emit("investigationSelection",{"president":DATA[room].president,
                    "players":DATA[room].getPlayers(), "board":DATA[room].board },
                        room=room)
                return

        if (DATA[room].board["F"] == 1 and DATA[room].size in [5,8,9,10]):
            DATA[room].specialPresidency = True
            emit("specialPresidency",{"president":DATA[room].president, 
                "players":DATA[room].getPlayers(), "board":DATA[room].board },
                    room=room)
            return

        if DATA[room].board["F"] == 3 and DATA[room].size in [5,6]:
            if len(DATA[room].deck) < 3:
                DATA[room].deck = DATA[room].deck + DATA[room].discard
                random.shuffle(DATA[room].deck)
            topCard = DATA[room].deck[0]
            emit("showTopCard",{"president":DATA[room].president,"card":topCard, 
                "board":DATA[room].board}, room = room)
            return 

        if DATA[room].board["F"] in [4,5]:
            emit("executePlayer", {"president":DATA[room],"players":DATA[room].getPlayers(),
            "board":DATA[room].board},room=room)
            return

    president = DATA[room].nextPresident()  
    chancellors = DATA[room].getChancellorCandidates()
    emit("president",{"president":president,"chancellorCandidates":chancellors,"board":DATA[room].board},room=room)

@socketio.on("investigationResponse")
def checkPlayer(selectedPlayer, room):
    print(selectedPlayer)
    for player in DATA[room].players:
        if player.name == selectedPlayer:
            playerRole = player.role
            if playerRole == "H":
                playerRole = "F"
            print(playerRole)
            emit("playerRoleReveal", playerRole)
    DATA[room].investigation = False

@socketio.on("getBoard")
def handleGetBoard(room):
    emit("getBoardResponse",DATA[room].board)

@socketio.on("specialPresidencySelection")
def handleSPSelection(president,room):
    DATA[room].president = president
    presidentData = {
        "president": president, 
        "chancellorCandidates": DATA[room].getPlayers(),
        "board":DATA[room].board
    }
    emit("president", presidentData, room=room)   

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.environ.get("PORT", 3000), debug=True)
    socketio.run(app)