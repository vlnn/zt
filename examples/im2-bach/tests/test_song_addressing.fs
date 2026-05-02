include test-lib.fs
require ../app/music.fs

\ step-addr for index 0 is the song base, then advances by 4 bytes per step
: test-step-addr-zero       0 step-addr  song assert-eq ;
: test-step-addr-one        1 step-addr  song 4 + assert-eq ;
: test-step-addr-ten       10 step-addr  song 40 + assert-eq ;

\ Step 0 of BWV 775 voice 1 is D4 (period 377), voice 2 is silent (0).
: test-step-0-voice-a       0 step-period-a   377 assert-eq ;
: test-step-0-voice-b       0 step-period-b     0 assert-eq ;

\ Step 6 (= bar 2 first 16th) of voice 1 is C#4 (period 400).
: test-step-6-voice-a       6 step-period-a   400 assert-eq ;

\ Voice 2 enters at step 12 with D3 (period 755); voice 1 at step 12 plays F4.
: test-step-12-voice-a     12 step-period-a   317 assert-eq ;
: test-step-12-voice-b     12 step-period-b   755 assert-eq ;

\ Final fermata: last 6 steps are D4 / D2 (period 377 / 1510).
: test-step-end-voice-a   311 step-period-a   377 assert-eq ;
: test-step-end-voice-b   311 step-period-b  1510 assert-eq ;

\ wrap-step rolls song-length back to 0 but leaves smaller indices alone
: test-wrap-mid           150 wrap-step       150 assert-eq ;
: test-wrap-at-length     song-length wrap-step  0 assert-eq ;
