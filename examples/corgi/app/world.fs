require core.fs

5 constant n-rooms

0 constant kitchen
1 constant hallway
2 constant garden
3 constant road
4 constant well

0 constant dir-n
1 constant dir-s
2 constant dir-e
3 constant dir-w

create exits-table 40 allot

: room-base    ( room -- addr )       4 *  2 *  exits-table + ;
: exit-cell    ( room dir -- addr )   swap room-base swap 2 * + ;
: exit-of      ( room dir -- target ) exit-cell @ ;
: blocked?     ( target -- flag )     -1 = ;

: clear-exits  exits-table 40 255 fill ;

: connect      ( target room dir -- ) exit-cell ! ;

: init-exits
    clear-exits
    hallway kitchen dir-n connect
    kitchen hallway dir-s connect
    garden  hallway dir-n connect
    hallway garden  dir-s connect
    road    garden  dir-n connect
    garden  road    dir-s connect
    well    road    dir-e connect
    road    well    dir-w connect ;

variable here-room

3 constant n-items

0 constant bone
1 constant stick
2 constant ball

-2 constant carried

create item-room 6 allot

: item-loc-addr  ( id -- addr )  2 *  item-room + ;
: item-room@     ( id -- room )  item-loc-addr @ ;
: item-room!     ( room id -- )  item-loc-addr ! ;

: place-items
    kitchen bone  item-room!
    garden  stick item-room!
    well    ball  item-room! ;

: carrying?    ( id -- flag )  item-room@ carried = ;
: here?        ( id -- flag )  item-room@ here-room @ = ;

: have-stick?  ( -- flag )  stick carrying? ;
