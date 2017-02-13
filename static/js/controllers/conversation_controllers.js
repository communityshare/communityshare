'use strict';

var angular = require( 'angular' );

var module = angular.module(
	'communityshare.controllers.conversation',
	[
		'communityshare.services.authentication',
		'communityshare.services.utility',
		'communityshare.services.conversation',
	] );

var combineMessages = function( baseMessage, specificMessage ) {
	var msg = '';
	if ( specificMessage ) {
		msg = ': ' + specificMessage;
	}
	var message = baseMessage + msg;
	return message;
};

module.controller(
	'MessagesController',
	[ '$scope', 'Session', 'Conversation', '$location', '$modal', function( $scope, Session, Conversation, $location, $modal ) {
		$scope.Session = Session;
		var user = Session.activeUser;
		if ( user ) {
			var conversationsPromise = Conversation.get_many( { 'user_id': user.id }, true );
			conversationsPromise.then(
				function( conversations ) {
					conversations.sort( function( a, b ) {
						return a.datetime_last_message < b.datetime_last_message;
					} );
					$scope.conversations = conversations;
				} );
		}
		$scope.showConversation = function( conversationId ) {
			$location.path( '/conversation/' + conversationId );
		};

		$scope.showThankYou = function() {
			$modal.open( {
				templateUrl: './static/templates/community_partner_thankyou.html',
				controller: 'ModalController',
			} );
		};

		var showModal = $location.search().first;
		if ( showModal ) {
			$scope.showThankYou();
		}
	} ] );

module.controller(
	'ConversationController',
	[ '$scope', '$q', '$location', '$timeout', '$modal', 'Session', 'Conversation', 'Message', 'User', 'Share', 'makeDialog', 'conversation', function( $scope, $q, $location, $timeout, $modal, Session,
																																						Conversation, Message, User, Share, makeDialog, conversation ) {
		$scope.Session = Session;
		if ( ( conversation === undefined ) || ( Session.activeUser === undefined ) ) {
			return;
		}

		Share.get_many( { conversation_id: conversation.id } );
		$scope.otherUser = undefined;
		$scope.conversation = conversation;
		$scope.newMessage = undefined;
		var makeNewMessage = function() {
			var newMessage = new Message( {
				conversation_id: conversation.id,
				sender_user_id: Session.activeUser.id,
				content: '',
			} );
			return newMessage;
		};
		var showErrorMessage = function( message ) {
			var baseMessage = 'Failed to load conversation';
			var msg = combineMessages( baseMessage, message );
			$scope.errorMessage = msg;
		};
		var refreshConversation = function() {
			var refreshedConversationPromise = Conversation.get( conversation.id, true );
			refreshedConversationPromise.then(
				function( conversation ) {
					$scope.conversation = conversation;
					$timeout( refreshConversation, 5000 );
					$scope.conversationErrorMessage = '';
				},
				function( message ) {
					var baseMessage = 'Failed to load conversation';
					var msg = combineMessages( baseMessage, message );
					$scope.conversationErrorMessage = msg;
				}
			);
		};
		var refreshShares = function() {
			var refreshedSharesPromise = Share.get_many( { conversation_id: conversation.id }, true );
			refreshedSharesPromise.then(
				function( shares ) {
					sortShares( shares );
					$scope.shares = shares;
					$timeout( refreshShares, 5000 );
					$scope.sharesErrorMessage = '';
				},
				function( message ) {
					var baseMessage = 'Failed to load shares';
					var msg = combineMessages( baseMessage, message );
					$scope.sharesErrorMessage = msg;
				}
			);
		};
		conversation.markMessagesAsViewed();
		if ( conversation.userA.id === Session.activeUser.id ) {
			$scope.otherUser = conversation.userB;
		} else {
			$scope.otherUser = conversation.userA;
		}
		$scope.messageHighlightClasses = {};
		$scope.messageHighlightClasses[ Session.activeUser.id ] = 'highlight1';
		$scope.messageHighlightClasses[ $scope.otherUser.id ] = 'highlight2';
		$scope.newMessage = makeNewMessage();
		// refreshShares();
		// $timeout( refreshConversation, 5000 );
		$scope.createNewShare = function() {
			var share = conversation.makeShare();
			$scope.editShare( share );
		};
		$scope.editShare = function( share ) {
			var opts = {
				templateUrl: './static/templates/share_edit.html',
				controller: 'EditShareController',
				resolve: {
					share: function() {
						return share;
					},
				},
			};
			$modal.open( opts );
		};
		var sortShares = function( shares ) {
			var sortedShares = Share.sortShares( shares );
			$scope.futureShares = sortedShares.future;
			$scope.pastShares = sortedShares.past;
		};
		$scope.sendMessage = function() {
			var messagePromise = $scope.newMessage.save();
			messagePromise.then(
				function( message ) {
					message.sender_user = Session.activeUser;
					$scope.conversation.messages.push( message );
					$scope.newMessage = makeNewMessage();
				},
				showErrorMessage
			);
		};
		$scope.now = new Date();
		$scope.reviewEvent = function( event ) {
			$location.path( '/event/' + event.id );
		};
		$scope.confirmShare = function( share ) {
			// Saving with no changes acts as an approve.
			share.save();
		};
		$scope.cancelShare = function( share ) {
			var title = 'Cancel Share';
			var msg = 'Do you really want to cancel this share with ' +
				$scope.otherUser.name;
			var btns = [ { result: 'yes', label: 'Yes', cssClass: 'btn-primary' },
				{ result: 'no', label: 'No' } ];
			var d = makeDialog( title, msg, btns );
			d.result.then(
				function( result ) {
					if ( result === 'yes' ) {
						// FIXME: Send email to otherUser saying they want to cancel it.
						var deletePromise = share.destroy();
						deletePromise.then(
							function() {
							},
							function( message ) {
								var baseMessage = 'Failed to cancel share';
								var msg = combineMessages( baseMessage, message );
								$scope.errorMessage = msg;
							} );
					}
				} );
		};
	} ] );

module.controller(
	'NewConversationController',
	[ 'Session', '$scope', '$modalInstance', 'userId', 'searchId', 'User', 'Conversation', 'Message', 'Authenticator', 'Messages',
		function( Session, $scope, $modalInstance, userId, searchId, User, Conversation, Message, Authenticator, Messages ) {
			var userPromise = User.get( userId );
			$scope.Session = Session;
			$scope.errorMessage = '';
			if ( ! Session.activeUser.email_confirmed ) {
				// Refresh active User to make sure email is still unconfirmed.
				User.get( Session.activeUser.id, true );
			}
			$scope.conversation = new Conversation( {
				title: undefined,
				search_id: searchId,
				userA_id: Session.activeUser.id,
				userB_id: userId,
			} );
			$scope.resendEmailConfirmation = function() {
				var emailConfirmPromise = Authenticator.requestConfirmEmail();
				emailConfirmPromise.then(
					function() {
						Messages.info( 'Sent email confirmation email.' );
					},
					function( errorMessage ) {
						Messages.error( errorMessage );
					} );
			};
			$scope.message = new Message( {
				conversation_id: undefined,
				sender_user_id: Session.activeUser.id,
				content: undefined,
			} );
			userPromise.then(
				function( user ) {
					$scope.user = user;
				} );
			$scope.cancel = function() {
				$modalInstance.close();
			};
			$scope.startConversation = function() {
				var conversationPromise = $scope.conversation.save();
				conversationPromise.then(
					function( conversation ) {
						$scope.errorMessage = '';
						$scope.message.conversation_id = conversation.id;
						var messagePromise = $scope.message.save();
						messagePromise.then(
							function() {
								$modalInstance.close( conversation );
							},
							function( message ) {
								var baseMessage = 'Failed to save message';
								$scope.errorMessage = combineMessages( baseMessage, message );
							} );
					},
					function( message ) {
						var baseMessage = 'Failed to save conversation';
						$scope.errorMessage = combineMessages( baseMessage, message );
					} );
			};
		} ] );

