'use strict';

var angular = require( 'angular' );

var module = angular.module( 'communityshare.directives.institutions', [
	'communityshare.services.user',
] );

module.directive(
	'csInstitutions',
	[ 'Session', 'Institution', function( Session, Institution ) {
		return {
			scope: {
				user: '=',
				methods: '=',
				isEducator: '@',
				isCommunityPartner: '@',
			},
			templateUrl: './static/templates/institution_adder.html',
			controller: [ '$scope', function( $scope ) {
				$scope.isEducator = ( $scope.isEducator === 'true' );
				$scope.isCommunityPartner = ( $scope.isCommunityPartner === 'true' );
				$scope.updateInstitutions = function() {
					if ( $scope.noInstitutions ) {
						$scope.user.institution_associations = [];
						$scope.user.addNewInstitutionAssociation();
						$scope.institutionsForm.submitted = false;
					}
				};
				$scope.$watch( 'institutionsForm', function() {
					$scope.methods.form = $scope.institutionsForm;
				} );
				$scope.methods.isValid = function() {
					return $scope.institutionsForm.$valid || $scope.noInstitutions;
				};
				// FIXME: Not scaleable.  Change to get the most popular.
				var institutionsPromise = Institution.get_many();
				$scope.options = {
					institutions: [],
					institutionTypes: [],
				};
				if ( $scope.isCommunityPartner ) {
					$scope.institutionTypes = [
						'Corporation', 'Freelancer', 'Nonprofit', 'Academic',
						'Government', 'Other',
					];
					$scope.roles = [];
				} else if ( $scope.isEducator ) {
					$scope.institutionTypes = [
						'Public District School',
						'Public Charter',
						'Private School',
						'Home School',
						'Higher Education',
						'Nonprofit',
						'After School Program',
						'Other',
					];
					$scope.roles = [
						'Classroom Teacher',
						'Curriculum Coordinator',
						'Administrator',
						'Parent',
						'Other',
					];
				}
				if ( $scope.user.institution_associations.length === 0 ) {
					$scope.user.institution_associations.push( { institution: {} } );
				}
				institutionsPromise.then(
					function( institutions ) {
						$scope.institutions = institutions;
					} );
			} ],
		};
	} ] );

module.directive(
	'csInstitutionAssociationEdit',
	function() {
		return {
			templateUrl: 'static/templates/institution_association.html',
			controller: [ '$scope', function( $scope ) {
				$scope.$watch( 'institutionsForm.submitted', function() {
					if ( $scope.institutionsForm ) {
						$scope.submitted = $scope.institutionsForm.submitted;
					}
				} );
			} ],
		};
	} );

